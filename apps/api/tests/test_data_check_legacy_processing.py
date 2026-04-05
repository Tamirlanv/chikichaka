"""Legacy run.overall_status 'processing' must be visible to sweep/SLA queries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from invision_api.models.enums import ApplicationStage, DataCheckRunStatus
from invision_api.repositories import data_check_repository
from invision_api.services.data_check import submit_bootstrap_service
from invision_api.services.data_check.orchestrator_service import RUN_PROCESSING_SLA_MINUTES_DEFAULT


def test_list_stuck_runs_includes_legacy_processing_overall_status(db: Session, factory, monkeypatch) -> None:
    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_a, **_kwargs: None)

    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    app.current_stage = ApplicationStage.initial_screening.value
    db.flush()

    run_id = submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )
    run = data_check_repository.get_run(db, run_id)
    assert run is not None
    run.overall_status = "processing"
    stale_time = datetime.now(tz=UTC) - timedelta(minutes=30)
    run.updated_at = stale_time
    db.flush()

    threshold = datetime.now(tz=UTC) - timedelta(minutes=10)
    stuck = data_check_repository.list_stuck_runs(db, stale_threshold=threshold)
    assert any(r.id == run_id for r in stuck)


def test_list_runs_past_processing_sla_includes_legacy_processing(db: Session, factory, monkeypatch) -> None:
    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_a, **_kwargs: None)

    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    app.current_stage = ApplicationStage.initial_screening.value
    db.flush()

    run_id = submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )
    run = data_check_repository.get_run(db, run_id)
    assert run is not None
    run.overall_status = "processing"
    old_created = datetime.now(tz=UTC) - timedelta(minutes=RUN_PROCESSING_SLA_MINUTES_DEFAULT + 10)
    run.created_at = old_created
    db.flush()

    sla_deadline = datetime.now(tz=UTC) - timedelta(minutes=RUN_PROCESSING_SLA_MINUTES_DEFAULT)
    sla_runs = data_check_repository.list_runs_past_processing_sla(db, sla_deadline=sla_deadline)
    assert any(r.id == run_id for r in sla_runs)


def test_bootstrap_idempotent_when_existing_run_is_legacy_processing(db: Session, factory, monkeypatch) -> None:
    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_a, **_kwargs: None)

    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    app.current_stage = ApplicationStage.initial_screening.value
    db.flush()

    first = submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )
    run = data_check_repository.get_run(db, first)
    assert run is not None
    run.overall_status = "processing"
    db.flush()

    second = submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )
    assert second == first


def test_bootstrap_run_overall_status_is_pending(db: Session, factory, monkeypatch) -> None:
    """New runs use ``pending`` (migration normalizes legacy ``processing`` rows in DB)."""
    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_a, **_kwargs: None)

    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    app.current_stage = ApplicationStage.initial_screening.value
    db.flush()

    run_id = submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )
    run = data_check_repository.get_run(db, run_id)
    assert run is not None
    assert run.overall_status == DataCheckRunStatus.pending.value


def test_bootstrap_creates_new_canonical_run_when_only_active_run_is_noncanonical(
    db: Session, factory, monkeypatch
) -> None:
    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_a, **_kwargs: None)

    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    app.current_stage = ApplicationStage.initial_screening.value
    db.flush()

    legacy = data_check_repository.create_run(
        db,
        candidate_id=profile.id,
        application_id=app.id,
        status=DataCheckRunStatus.running.value,
    )
    data_check_repository.create_check(
        db,
        run_id=legacy.id,
        check_type="links",
        status="running",
        result_payload=None,
    )
    db.flush()

    run_id = submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )
    assert run_id != legacy.id
    assert data_check_repository.run_has_canonical_policy_checks(db, run_id) is True


def test_bootstrap_prefers_active_canonical_run_over_newer_noncanonical(
    db: Session, factory, monkeypatch
) -> None:
    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_a, **_kwargs: None)

    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    app.current_stage = ApplicationStage.initial_screening.value
    db.flush()

    canonical_id = submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )
    noncanonical = data_check_repository.create_run(
        db,
        candidate_id=profile.id,
        application_id=app.id,
        status=DataCheckRunStatus.running.value,
    )
    data_check_repository.create_check(
        db,
        run_id=noncanonical.id,
        check_type="links",
        status="running",
        result_payload=None,
    )
    db.flush()

    second = submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )
    assert second == canonical_id
