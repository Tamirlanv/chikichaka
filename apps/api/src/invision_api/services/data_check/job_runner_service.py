from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

import logging

from invision_api.models.enums import (
    ApplicationStage,
    DataCheckRunStatus,
    DataCheckUnitStatus,
    DataCheckUnitType,
    JobStatus,
)
from invision_api.repositories import admissions_repository, commission_repository, data_check_repository
from invision_api.services.data_check import orchestrator_service
from invision_api.services.data_check import reconcile_service
from invision_api.services.data_check.job_registry import REGISTRY
from invision_api.services.data_check.status_service import (
    TERMINAL_UNIT_STATUSES,
    RunStatusComputation,
    compute_run_status,
)
from invision_api.services.stage_transition_policy import TransitionContext, TransitionName, apply_transition

logger = logging.getLogger(__name__)


def _update_analysis_job(
    db: Session,
    *,
    analysis_job_id: UUID | None,
    status: str,
    last_error: str | None = None,
) -> None:
    if not analysis_job_id:
        return
    job = admissions_repository.get_analysis_job(db, analysis_job_id)
    if not job:
        return
    admissions_repository.update_analysis_job(
        db,
        job,
        status=status,
        attempts=(job.attempts or 0) + 1 if status in {JobStatus.running.value, JobStatus.failed.value} else job.attempts,
        last_error=last_error,
    )


# Only a fully successful pipeline may auto-advance. ``partial`` means at least one
# unit needs attention (optional failure, optional/required manual review, etc.) and
# must not move the application to application_review without an explicit commission action.
_ADVANCE_STATUSES = {DataCheckRunStatus.ready.value}


def _aggregate_status_for_run(db: Session, run_id: UUID) -> RunStatusComputation:
    """Recompute run aggregate from DB checks (source of truth for batch completion).

    ``partial`` / ``failed`` / ``ready`` are only produced when every policy unit is in a
    terminal unit status; until then the aggregate stays ``pending`` or ``running``. Skip
    decisions must use this recomputation, not only ``run.overall_status``, so a stale row
    cannot block remaining units or drop jobs while work is still outstanding.
    """
    checks = data_check_repository.list_checks_for_run(db, run_id)
    status_map: dict[DataCheckUnitType, str] = {}
    for c in checks:
        try:
            status_map[DataCheckUnitType(c.check_type)] = c.status
        except ValueError:
            continue
    return compute_run_status(status_map)


def _try_auto_advance(
    db: Session,
    *,
    run_computed: object,
    app: object | None,
    application_id: UUID,
) -> None:
    """Auto-advance from initial_screening to application_review.

    Fires only when the data-check run is ``ready`` (all units completed successfully
    with no optional failures and no manual-review flags). ``partial`` and ``failed``
    keep the application on initial_screening for follow-up or manual handling.
    """
    run_status = getattr(run_computed, "status", None)

    if not app:
        logger.warning("auto_advance_skip application=%s reason=app_is_none", application_id)
        return
    if run_status not in _ADVANCE_STATUSES:
        logger.info("auto_advance_skip application=%s reason=status_not_ready run_status=%s", application_id, run_status)
        return

    try:
        db.refresh(app)
    except Exception:
        logger.warning("auto_advance_skip application=%s reason=refresh_failed", application_id)
        return
    if app.current_stage != ApplicationStage.initial_screening.value:
        logger.info(
            "auto_advance_skip application=%s reason=wrong_stage_after_refresh stage=%s",
            application_id,
            app.current_stage,
        )
        return

    note = "Auto-advanced: all data-check units completed successfully."
    logger.info("auto_advance_firing application=%s run_status=%s", application_id, run_status)
    try:
        apply_transition(
            db,
            app,
            TransitionContext(
                application_id=app.id,
                transition=TransitionName.screening_passed,
                actor_user_id=None,
                actor_type="system",
                internal_note=note,
            ),
        )
        commission_repository.upsert_projection_for_application(db, app)
        logger.info("auto_advance_ok application=%s initial_screening -> application_review", application_id)
    except ValueError as exc:
        if "only from initial_screening" in str(exc):
            logger.info("auto_advance_skip application=%s reason=idempotent stage_already_moved", application_id)
            return
        logger.exception("auto_advance_failed application=%s", application_id)
    except Exception:
        logger.exception("auto_advance_failed application=%s", application_id)


def run_unit(
    db: Session,
    *,
    application_id: UUID,
    run_id: UUID,
    unit_type: DataCheckUnitType,
    analysis_job_id: UUID | None = None,
) -> None:
    run = data_check_repository.get_run(db, run_id)
    if not run:
        _update_analysis_job(db, analysis_job_id=analysis_job_id, status=JobStatus.failed.value, last_error="run_not_found")
        return
    if not data_check_repository.run_has_canonical_policy_checks(db, run_id):
        logger.warning(
            "run_unit_skip non_canonical_run run=%s unit=%s",
            run_id,
            unit_type.value,
        )
        _update_analysis_job(db, analysis_job_id=analysis_job_id, status=JobStatus.completed.value)
        return
    check = data_check_repository.get_check(db, run_id, unit_type.value)
    if not check:
        _update_analysis_job(
            db,
            analysis_job_id=analysis_job_id,
            status=JobStatus.failed.value,
            last_error=f"check_not_found:{unit_type.value}",
        )
        return

    aggregate = _aggregate_status_for_run(db, run_id)
    if aggregate.status not in {
        DataCheckRunStatus.pending.value,
        DataCheckRunStatus.running.value,
    }:
        logger.info(
            "run_unit_skip batch_complete run=%s aggregate=%s unit=%s",
            run_id,
            aggregate.status,
            unit_type.value,
        )
        _update_analysis_job(db, analysis_job_id=analysis_job_id, status=JobStatus.completed.value)
        return

    if check.status in TERMINAL_UNIT_STATUSES:
        logger.info(
            "run_unit_skip terminal_check run=%s unit=%s check_status=%s",
            run_id,
            unit_type.value,
            check.status,
        )
        try:
            orchestrator_service.enqueue_ready_followup_jobs(db, application_id=application_id, run_id=run_id)
        except Exception:
            logger.exception("followup_enqueue_failed application=%s run=%s", application_id, run_id)
        _update_analysis_job(db, analysis_job_id=analysis_job_id, status=JobStatus.completed.value)
        return

    _update_analysis_job(db, analysis_job_id=analysis_job_id, status=JobStatus.running.value)

    now = datetime.now(tz=UTC)
    claimed_check = data_check_repository.try_claim_unit_check_for_execution(
        db,
        run_id=run_id,
        check_type=unit_type.value,
    )
    if not claimed_check:
        latest_check = data_check_repository.get_check(db, run_id, unit_type.value)
        if latest_check and latest_check.status in TERMINAL_UNIT_STATUSES:
            logger.info(
                "run_unit_skip unit_already_terminal_after_claim run=%s unit=%s status=%s",
                run_id,
                unit_type.value,
                latest_check.status,
            )
        else:
            logger.info(
                "run_unit_skip claim_not_acquired run=%s unit=%s current_status=%s",
                run_id,
                unit_type.value,
                latest_check.status if latest_check else "missing",
            )
        _update_analysis_job(db, analysis_job_id=analysis_job_id, status=JobStatus.completed.value)
        return
    check = claimed_check
    data_check_repository.upsert_unit_result(
        db,
        run_id=run_id,
        application_id=application_id,
        unit_type=unit_type.value,
        status=DataCheckUnitStatus.running.value,
        result_payload=check.result_payload,
        warnings=[],
        errors=[],
        explainability=[],
        manual_review_required=False,
        attempts=check.attempts,
        started_at=check.started_at or now,
        finished_at=None,
    )
    if run.overall_status in {DataCheckRunStatus.pending.value, "processing"}:
        data_check_repository.update_run_status(
            db,
            run=run,
            status=DataCheckRunStatus.running.value,
            explainability=["Data-check pipeline started processing units."],
        )
    commission_repository.set_stage_status(
        db,
        application_id=application_id,
        stage=ApplicationStage.initial_screening.value,
        status="in_review",
        actor_user_id=None,
        reason_comment=f"Data-check unit started: {unit_type.value}",
    )
    db.flush()

    processor = REGISTRY[unit_type]
    _t0 = time.monotonic()
    logger.info(
        "data_check_unit_start run_id=%s application_id=%s unit_type=%s",
        run_id,
        application_id,
        unit_type.value,
    )
    try:
        result = processor(db, application_id, run.candidate_id, run_id)
        final_status = result.status
        if final_status not in {
            DataCheckUnitStatus.completed.value,
            DataCheckUnitStatus.failed.value,
            DataCheckUnitStatus.manual_review_required.value,
        }:
            final_status = DataCheckUnitStatus.failed.value
            result.errors.append(f"Unsupported unit status: {result.status}")
        data_check_repository.update_check_status(
            db,
            check=check,
            status=final_status,
            result_payload=result.payload,
            last_error="; ".join(result.errors) if result.errors else None,
        )
        data_check_repository.upsert_unit_result(
            db,
            run_id=run_id,
            application_id=application_id,
            unit_type=unit_type.value,
            status=final_status,
            result_payload=result.payload,
            warnings=result.warnings,
            errors=result.errors,
            explainability=result.explainability,
            manual_review_required=result.manual_review_required,
            attempts=check.attempts,
            started_at=check.started_at,
            finished_at=check.finished_at,
        )
    except Exception as exc:  # noqa: BLE001
        err_text = str(exc)
        data_check_repository.update_check_status(
            db,
            check=check,
            status=DataCheckUnitStatus.failed.value,
            last_error=err_text,
        )
        data_check_repository.upsert_unit_result(
            db,
            run_id=run_id,
            application_id=application_id,
            unit_type=unit_type.value,
            status=DataCheckUnitStatus.failed.value,
            result_payload=None,
            warnings=[],
            errors=[err_text],
            explainability=["Unit execution raised an exception."],
            manual_review_required=True,
            attempts=check.attempts,
            started_at=check.started_at,
            finished_at=check.finished_at,
        )
    finally:
        elapsed_ms = int((time.monotonic() - _t0) * 1000)
        logger.info(
            "data_check_unit_processor_done run_id=%s application_id=%s unit_type=%s elapsed_ms=%s",
            run_id,
            application_id,
            unit_type.value,
            elapsed_ms,
        )

    run_computed = _aggregate_status_for_run(db, run_id)
    app = reconcile_service.persist_initial_screening_after_aggregate(
        db,
        run=run,
        run_computed=run_computed,
        application_id=application_id,
    )

    logger.info(
        "run_unit_completed unit=%s application=%s computed_status=%s app_stage=%s",
        unit_type.value,
        application_id,
        run_computed.status,
        getattr(app, "current_stage", None) if app else "no_app",
    )
    _try_auto_advance(db, run_computed=run_computed, app=app, application_id=application_id)

    try:
        orchestrator_service.enqueue_ready_followup_jobs(db, application_id=application_id, run_id=run_id)
    except Exception:
        logger.exception("followup_enqueue_failed application=%s run=%s", application_id, run_id)

    final_check = data_check_repository.get_check(db, run_id, unit_type.value)
    if final_check and final_check.status == DataCheckUnitStatus.failed.value:
        _update_analysis_job(
            db,
            analysis_job_id=analysis_job_id,
            status=JobStatus.failed.value,
            last_error=final_check.last_error,
        )
    else:
        _update_analysis_job(db, analysis_job_id=analysis_job_id, status=JobStatus.completed.value)
