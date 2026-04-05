from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from invision_api.commission.application.personal_info_service import (
    get_commission_application_personal_info,
)
from invision_api.commission.application.personal_info_validators import resolve_commission_actions
from invision_api.models.commission import CommissionUser
from invision_api.models.enums import ApplicationState, DataCheckUnitType
from invision_api.models.user import Role
from invision_api.repositories import data_check_repository
from invision_api.services.data_check import submit_bootstrap_service


def test_actions_for_viewer_reviewer_and_admin(db: Session, factory):
    committee_role = factory.committee_role(db)

    viewer = factory.user(db)
    factory.assign_role(db, viewer, committee_role)
    db.add(CommissionUser(user_id=viewer.id, role="viewer"))

    reviewer = factory.user(db)
    factory.assign_role(db, reviewer, committee_role)
    db.add(CommissionUser(user_id=reviewer.id, role="reviewer"))

    admin_user = factory.user(db)
    admin_role = db.query(Role).filter(Role.name == "admin").first()
    if not admin_role:
        admin_role = Role(id=uuid4(), name="admin")
        db.add(admin_role)
        db.flush()
    factory.assign_role(db, admin_user, admin_role)
    db.flush()

    viewer_actions = resolve_commission_actions(db, viewer, can_advance_stage=True)
    reviewer_actions = resolve_commission_actions(db, reviewer, can_advance_stage=True)
    admin_actions = resolve_commission_actions(db, admin_user, can_advance_stage=True)

    assert viewer_actions == {
        "canComment": False,
        "canMoveForward": False,
        "canApproveAiInterview": False,
        "canGenerateAiInterview": False,
    }
    assert reviewer_actions == {
        "canComment": True,
        "canMoveForward": True,
        "canApproveAiInterview": False,
        "canGenerateAiInterview": False,
    }
    assert admin_actions == {
        "canComment": True,
        "canMoveForward": True,
        "canApproveAiInterview": False,
        "canGenerateAiInterview": False,
    }


def test_personal_info_opens_on_any_post_submit_stage(db: Session, factory):
    """After stage-gate removal, personal-info must return 200 on any stage."""
    committee_user = factory.user(db)
    committee_role = factory.committee_role(db)
    factory.assign_role(db, committee_user, committee_role)
    db.add(CommissionUser(user_id=committee_user.id, role="reviewer"))

    candidate_user = factory.user(db)
    profile = factory.profile(db, candidate_user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.locked_after_submit = True
    app.submitted_at = datetime.now(tz=UTC)
    app.current_stage = "committee_review"
    db.flush()

    result = get_commission_application_personal_info(db, application_id=app.id, actor=committee_user)
    assert result["applicationId"] == str(app.id)
    assert result["candidateSummary"]["currentStage"] == "committee_decision"


def test_personal_info_returns_processing_status_on_initial_screening(db: Session, factory):
    """On initial_screening, processingStatus should be present (null if no run)."""
    committee_user = factory.user(db)
    committee_role = factory.committee_role(db)
    factory.assign_role(db, committee_user, committee_role)
    db.add(CommissionUser(user_id=committee_user.id, role="reviewer"))

    candidate_user = factory.user(db)
    profile = factory.profile(db, candidate_user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.locked_after_submit = True
    app.submitted_at = datetime.now(tz=UTC)
    app.current_stage = "initial_screening"
    db.flush()

    result = get_commission_application_personal_info(db, application_id=app.id, actor=committee_user)
    assert result["applicationId"] == str(app.id)
    assert result["candidateSummary"]["currentStage"] == "data_check"
    # No data-check run created yet, so processingStatus is null
    assert result["processingStatus"] is None


def test_advance_not_allowed_on_initial_screening(db: Session, factory):
    """canMoveForward must be False when stage is initial_screening."""
    committee_user = factory.user(db)
    committee_role = factory.committee_role(db)
    factory.assign_role(db, committee_user, committee_role)
    db.add(CommissionUser(user_id=committee_user.id, role="reviewer"))

    candidate_user = factory.user(db)
    profile = factory.profile(db, candidate_user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.locked_after_submit = True
    app.submitted_at = datetime.now(tz=UTC)
    app.current_stage = "initial_screening"
    db.flush()

    result = get_commission_application_personal_info(db, application_id=app.id, actor=committee_user)
    assert result["actions"]["canMoveForward"] is False
    assert result["actions"]["canComment"] is True


@pytest.mark.parametrize(
    ("unit_status", "expected_overall"),
    [("manual_review_required", "partial"), ("failed", "failed")],
)
def test_personal_info_allows_manual_move_for_orange_stage_one_and_uses_human_reasons(
    db: Session,
    factory,
    monkeypatch,
    unit_status: str,
    expected_overall: str,
) -> None:
    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_a, **_kwargs: None)

    committee_user = factory.user(db)
    committee_role = factory.committee_role(db)
    factory.assign_role(db, committee_user, committee_role)
    db.add(CommissionUser(user_id=committee_user.id, role="reviewer"))

    candidate_user = factory.user(db)
    profile = factory.profile(db, candidate_user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.locked_after_submit = True
    app.submitted_at = datetime.now(tz=UTC)
    app.current_stage = "initial_screening"
    db.flush()

    run_id = submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=committee_user.id,
    )
    for check in data_check_repository.list_checks_for_run(db, run_id):
        check.status = "completed"
        if check.check_type == DataCheckUnitType.growth_path_processing.value:
            check.status = unit_status
    db.flush()

    result = get_commission_application_personal_info(db, application_id=app.id, actor=committee_user)
    assert result["actions"]["canMoveForward"] is True
    assert result["processingStatus"]["overall"] == expected_overall

    joined = "; ".join(
        (result["processingStatus"].get("warnings") or []) + (result["processingStatus"].get("errors") or [])
    ).lower()
    assert "manual_review_required" not in joined
    assert "growth_path_processing" not in joined
    assert "путь" in joined
