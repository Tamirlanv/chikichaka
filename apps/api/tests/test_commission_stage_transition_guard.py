"""Guards for commission Kanban stage advance (resolve_kanban_advance / advance_stage)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from invision_api.commission.application import service as commission_service
from invision_api.commission.application.stage_transition_guard import (
    StageAdvanceBlockCode,
    resolve_kanban_advance,
)
from invision_api.models.application import InterviewSession
from invision_api.models.enums import ApplicationStage, ApplicationState, DataCheckUnitType
from invision_api.repositories import ai_interview_repository, data_check_repository
from invision_api.services.data_check import submit_bootstrap_service


def test_resolve_blocks_manual_advance_from_initial_screening(db: Session, factory) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.under_screening.value)
    app.current_stage = ApplicationStage.initial_screening.value
    app.locked_after_submit = True
    db.flush()

    r = resolve_kanban_advance(db, app.id)
    assert not r.allowed
    assert r.block_code == StageAdvanceBlockCode.MANUAL_FROM_DATA_CHECK_FORBIDDEN


@pytest.mark.parametrize("unit_status", ["manual_review_required", "failed"])
def test_resolve_allows_manual_advance_from_initial_screening_when_orange(
    db: Session,
    factory,
    monkeypatch,
    unit_status: str,
) -> None:
    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_a, **_kwargs: None)

    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.under_screening.value)
    app.current_stage = ApplicationStage.initial_screening.value
    app.locked_after_submit = True
    db.flush()

    run_id = submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )
    for check in data_check_repository.list_checks_for_run(db, run_id):
        check.status = "completed"
        if check.check_type == DataCheckUnitType.growth_path_processing.value:
            check.status = unit_status
    db.flush()

    r = resolve_kanban_advance(db, app.id)
    assert r.allowed is True
    assert r.transition is not None
    assert r.transition.value == "screening_passed"


def test_advance_from_application_review_requires_rubric_and_ai(db: Session, factory) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.under_review.value)
    app.current_stage = ApplicationStage.application_review.value
    app.locked_after_submit = True
    db.flush()

    r = resolve_kanban_advance(db, app.id)
    assert not r.allowed
    assert r.block_code in (
        StageAdvanceBlockCode.STAGE_ONE_NOT_READY,
        StageAdvanceBlockCode.RUBRIC_INCOMPLETE,
    )

    with pytest.raises(HTTPException) as exc:
        commission_service.advance_stage(db, app.id, user.id, None)
    assert exc.value.status_code == 409


def test_interview_advance_requires_ai_complete_schedule_past_outcome(db: Session, factory) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.interview_pending.value)
    app.current_stage = ApplicationStage.interview.value
    app.locked_after_submit = True
    db.flush()

    r0 = resolve_kanban_advance(db, app.id)
    assert not r0.allowed
    assert r0.block_code == StageAdvanceBlockCode.AI_INTERVIEW_INCOMPLETE

    qs = ai_interview_repository.upsert_draft(
        db,
        application_id=app.id,
        questions=[
            {"id": "q1", "questionText": "A?", "sortOrder": 0},
            {"id": "q2", "questionText": "B?", "sortOrder": 1},
            {"id": "q3", "questionText": "C?", "sortOrder": 2},
        ],
        generated_from_signals=None,
    )
    qs.candidate_completed_at = datetime.now(tz=UTC)
    db.flush()

    r1 = resolve_kanban_advance(db, app.id)
    assert not r1.allowed
    assert r1.block_code == StageAdvanceBlockCode.COMMISSION_INTERVIEW_NOT_SCHEDULED

    past = datetime.now(tz=UTC) - timedelta(days=1)
    sess = InterviewSession(
        application_id=app.id,
        session_index=0,
        interview_status="scheduled",
        scheduled_at=past,
        scheduled_by_user_id=user.id,
    )
    db.add(sess)
    db.flush()

    r2 = resolve_kanban_advance(db, app.id)
    assert not r2.allowed
    assert r2.block_code == StageAdvanceBlockCode.COMMISSION_INTERVIEW_OUTCOME_MISSING

    sess.outcome_recorded_at = datetime.now(tz=UTC)
    db.flush()

    r3 = resolve_kanban_advance(db, app.id)
    assert r3.allowed
    assert r3.transition is not None
