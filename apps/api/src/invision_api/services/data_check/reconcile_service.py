"""Central helpers to persist data-check aggregate state and commission read models."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.application import Application
from invision_api.models.candidate_validation_orchestration import CandidateValidationRun
from invision_api.models.enums import ApplicationStage, DataCheckRunStatus
from invision_api.repositories import commission_repository, data_check_repository
from invision_api.services.data_check.status_service import RunStatusComputation


def commission_stage_status_for_run_aggregate(run_status: str) -> str:
    """Map data-check run aggregate to ApplicationStageState.status for initial_screening."""
    if run_status in {DataCheckRunStatus.pending.value, DataCheckRunStatus.running.value}:
        return "in_review"
    if run_status == DataCheckRunStatus.ready.value:
        return "approved"
    if run_status in {DataCheckRunStatus.partial.value, DataCheckRunStatus.failed.value}:
        return "needs_attention"
    return "in_review"


def persist_initial_screening_after_aggregate(
    db: Session,
    *,
    run: CandidateValidationRun,
    run_computed: RunStatusComputation,
    application_id: UUID,
) -> Application | None:
    """Update run row, initial_screening stage status, attention flag, and commission projection.

    Single entry point for «recompute aggregate → persist → projection» after unit work
    on the first pipeline stage (keeps orchestration consistent with job_runner).
    """
    data_check_repository.update_run_status(
        db,
        run=run,
        status=run_computed.status,
        warnings=run_computed.warnings,
        errors=run_computed.errors,
        explainability=run_computed.explainability,
    )
    stage_status = commission_stage_status_for_run_aggregate(run_computed.status)
    commission_repository.set_stage_status(
        db,
        application_id=application_id,
        stage=ApplicationStage.initial_screening.value,
        status=stage_status,
        actor_user_id=None,
        reason_comment=f"Data-check status updated: {run_computed.status}",
    )
    commission_repository.set_attention_flag(
        db,
        application_id=application_id,
        stage=ApplicationStage.initial_screening.value,
        value=run_computed.manual_review_required,
    )
    app = data_check_repository.get_application(db, application_id)
    if app:
        commission_repository.upsert_projection_for_application(db, app)
    return app
