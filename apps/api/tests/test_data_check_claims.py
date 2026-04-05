from __future__ import annotations

from sqlalchemy.orm import Session

from invision_api.models.enums import ApplicationStage, DataCheckUnitType
from invision_api.repositories import data_check_repository
from invision_api.services.data_check import submit_bootstrap_service


def test_try_claim_unit_check_for_execution_is_single_winner(
    db: Session, factory, monkeypatch
) -> None:
    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_a, **_k: None)

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

    check_type = DataCheckUnitType.test_profile_processing.value
    claimed_first = data_check_repository.try_claim_unit_check_for_execution(
        db,
        run_id=run_id,
        check_type=check_type,
    )
    claimed_second = data_check_repository.try_claim_unit_check_for_execution(
        db,
        run_id=run_id,
        check_type=check_type,
    )
    db.flush()

    assert claimed_first is not None
    assert claimed_first.status == "running"
    assert claimed_first.attempts == 1
    assert claimed_second is None
