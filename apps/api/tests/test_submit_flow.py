"""Integration tests for the application submit flow."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import Application, ApplicationStageHistory
from invision_api.models.enums import ApplicationStage, ApplicationState
from invision_api.services.application_service import (
    REQUIRED_SECTIONS,
    completion_percentage,
    submit_application,
)


def test_submit_requires_verified_email(db: Session, factory):
    """Submit must reject users without verified email."""
    user = factory.user(db, verified=False)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    factory.fill_required_sections(db, app)
    db.commit()

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        submit_application(db, user)
    assert exc_info.value.status_code == 403


def test_submit_requires_all_sections_complete(db: Session, factory):
    """Submit with missing sections returns 400 with missing_sections list."""
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    db.commit()

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        submit_application(db, user)
    assert exc_info.value.status_code == 400
    assert "missing_sections" in str(exc_info.value.detail)


def test_submit_happy_path_sets_state_and_locks(db: Session, factory):
    """Successful submit sets state to under_screening, locks editing, records stage history."""
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="in_progress")
    factory.fill_required_sections(db, app)
    db.commit()

    # Mock the post-submit jobs to avoid Redis dependency
    import invision_api.services.stages.initial_screening_service as iss
    original = iss.enqueue_post_submit_jobs
    iss.enqueue_post_submit_jobs = lambda db, app_id: None

    try:
        result = submit_application(db, user)
        assert result.locked_after_submit is True
        assert result.state == ApplicationState.under_screening.value
        assert result.current_stage == ApplicationStage.initial_screening.value
        assert result.submitted_at is not None

        histories = list(db.scalars(
            select(ApplicationStageHistory)
            .where(ApplicationStageHistory.application_id == app.id)
            .order_by(ApplicationStageHistory.entered_at.desc())
        ).all())
        assert len(histories) >= 2
        latest = histories[0]
        assert latest.to_stage == ApplicationStage.initial_screening.value
    finally:
        iss.enqueue_post_submit_jobs = original


def test_submit_duplicate_returns_409(db: Session, factory):
    """Second submit on locked application returns 409."""
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="in_progress")
    factory.fill_required_sections(db, app)
    db.commit()

    import invision_api.services.stages.initial_screening_service as iss
    original = iss.enqueue_post_submit_jobs
    iss.enqueue_post_submit_jobs = lambda db, app_id: None

    try:
        submit_application(db, user)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            submit_application(db, user)
        assert exc_info.value.status_code == 409
    finally:
        iss.enqueue_post_submit_jobs = original


def test_completion_percentage_all_complete(db: Session, factory):
    """All required sections complete gives 100%."""
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    factory.fill_required_sections(db, app)
    db.flush()

    pct, missing = completion_percentage(db, app)
    assert pct == 100
    assert missing == []


def test_completion_percentage_missing_sections(db: Session, factory):
    """No sections filled gives 0%."""
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    db.flush()

    pct, missing = completion_percentage(db, app)
    assert pct == 0
    assert len(missing) == len(REQUIRED_SECTIONS)
