"""Integration tests for stage transition state machine."""

import pytest
from sqlalchemy.orm import Session

from invision_api.models.enums import ApplicationStage, ApplicationState
from invision_api.repositories import ai_interview_repository
from invision_api.services.stage_transition_policy import (
    TransitionContext,
    TransitionName,
    apply_transition,
)


def test_screening_passed_moves_to_application_review(db: Session, factory):
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    app.current_stage = ApplicationStage.initial_screening.value
    app.state = ApplicationState.under_screening.value
    db.flush()

    ctx = TransitionContext(
        application_id=app.id,
        transition=TransitionName.screening_passed,
        actor_user_id=user.id,
        actor_type="committee",
    )
    apply_transition(db, app, ctx)
    assert app.current_stage == ApplicationStage.application_review.value
    assert app.state == ApplicationState.under_review.value


def test_review_complete_moves_to_interview(db: Session, factory):
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    app.current_stage = ApplicationStage.application_review.value
    app.state = ApplicationState.under_review.value
    db.flush()

    questions = [
        {"id": "q1", "questionText": "A?", "sortOrder": 0},
        {"id": "q2", "questionText": "B?", "sortOrder": 1},
        {"id": "q3", "questionText": "C?", "sortOrder": 2},
    ]
    row = ai_interview_repository.upsert_draft(
        db,
        application_id=app.id,
        questions=questions,
        generated_from_signals=None,
    )
    ai_interview_repository.mark_approved(db, row, approved_by_user_id=user.id)

    ctx = TransitionContext(
        application_id=app.id,
        transition=TransitionName.review_complete,
        actor_user_id=user.id,
        actor_type="committee",
    )
    apply_transition(db, app, ctx)
    assert app.current_stage == ApplicationStage.interview.value


def test_review_complete_rejected_without_approved_ai_interview(db: Session, factory):
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    app.current_stage = ApplicationStage.application_review.value
    app.state = ApplicationState.under_review.value
    db.flush()

    ctx = TransitionContext(
        application_id=app.id,
        transition=TransitionName.review_complete,
        actor_user_id=user.id,
        actor_type="committee",
    )
    with pytest.raises(ValueError, match="одобрения"):
        apply_transition(db, app, ctx)


def test_interview_complete_moves_to_committee(db: Session, factory):
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    app.current_stage = ApplicationStage.interview.value
    db.flush()

    ctx = TransitionContext(
        application_id=app.id,
        transition=TransitionName.interview_complete,
        actor_user_id=user.id,
        actor_type="committee",
    )
    apply_transition(db, app, ctx)
    assert app.current_stage == ApplicationStage.committee_review.value


def test_committee_advances_to_decision(db: Session, factory):
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    app.current_stage = ApplicationStage.committee_review.value
    db.flush()

    ctx = TransitionContext(
        application_id=app.id,
        transition=TransitionName.human_advances_to_decision,
        actor_user_id=user.id,
        actor_type="committee",
    )
    apply_transition(db, app, ctx)
    assert app.current_stage == ApplicationStage.decision.value


def test_revision_required_unlocks_editing(db: Session, factory):
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    app.current_stage = ApplicationStage.initial_screening.value
    app.locked_after_submit = True
    db.flush()

    ctx = TransitionContext(
        application_id=app.id,
        transition=TransitionName.revision_required,
        actor_user_id=user.id,
        actor_type="committee",
    )
    apply_transition(db, app, ctx)
    assert app.locked_after_submit is False
    assert app.current_stage == ApplicationStage.application.value
    assert app.state == ApplicationState.revision_required.value
