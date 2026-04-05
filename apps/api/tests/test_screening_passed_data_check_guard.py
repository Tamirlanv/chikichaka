"""Manual screening_passed must match data-check readiness (no bypass unless break-glass)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from invision_api.models.enums import ApplicationStage, ApplicationState, DataCheckUnitType
from invision_api.repositories import data_check_repository
from invision_api.services.data_check import job_registry, submit_bootstrap_service
from invision_api.services.data_check.contracts import UnitExecutionResult
from invision_api.services.data_check import job_runner_service
from invision_api.services.stages import initial_screening_service


_EXECUTION_ORDER = (
    DataCheckUnitType.test_profile_processing,
    DataCheckUnitType.motivation_processing,
    DataCheckUnitType.growth_path_processing,
    DataCheckUnitType.achievements_processing,
    DataCheckUnitType.link_validation,
    DataCheckUnitType.video_validation,
    DataCheckUnitType.certificate_validation,
    DataCheckUnitType.signals_aggregation,
    DataCheckUnitType.candidate_ai_summary,
)


def _bootstrap(db: Session, factory, monkeypatch):
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.under_screening.value)
    app.current_stage = ApplicationStage.initial_screening.value
    app.locked_after_submit = True
    db.flush()

    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_a, **_k: None)

    run_id = submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )
    return user, profile, app, run_id


def test_manual_screening_passed_rejected_when_pipeline_not_ready(db: Session, factory, monkeypatch):
    user, _, app, run_id = _bootstrap(db, factory, monkeypatch)

    def _ok(*_a, **_k):
        return UnitExecutionResult(status="completed", payload={"ok": True})

    monkeypatch.setitem(job_registry.REGISTRY, DataCheckUnitType.test_profile_processing, _ok)
    job_runner_service.run_unit(
        db,
        application_id=app.id,
        run_id=run_id,
        unit_type=DataCheckUnitType.test_profile_processing,
        analysis_job_id=None,
    )
    monkeypatch.setattr(job_runner_service, "_try_auto_advance", lambda *_a, **_k: None)

    with pytest.raises(HTTPException) as exc:
        initial_screening_service.ensure_manual_screening_passed_allowed(db, application_id=app.id, user=user)
    assert exc.value.status_code == 409
    assert isinstance(exc.value.detail, dict)
    assert exc.value.detail.get("code") == "DATA_CHECK_NOT_READY"


def test_manual_screening_passed_allowed_when_pipeline_ready(db: Session, factory, monkeypatch):
    user, _, app, run_id = _bootstrap(db, factory, monkeypatch)

    def _ok(*_a, **_k):
        return UnitExecutionResult(status="completed", payload={"ok": True})

    for unit in DataCheckUnitType:
        monkeypatch.setitem(job_registry.REGISTRY, unit, _ok)

    monkeypatch.setattr(job_runner_service, "_try_auto_advance", lambda *_a, **_k: None)

    for unit in _EXECUTION_ORDER:
        job_runner_service.run_unit(
            db,
            application_id=app.id,
            run_id=run_id,
            unit_type=unit,
            analysis_job_id=None,
        )

    run = data_check_repository.get_run(db, run_id)
    assert run is not None
    assert run.overall_status == "ready"

    initial_screening_service.ensure_manual_screening_passed_allowed(db, application_id=app.id, user=user)
