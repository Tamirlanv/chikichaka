"""Commission archive-delete: history row + fresh candidate application."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from invision_api.commission.application import service as commission_service
from invision_api.models.enums import ApplicationStage, ApplicationState
from invision_api.repositories import commission_repository
from invision_api.repositories.application_repository import get_application_for_candidate


def test_archive_by_commission_marks_old_and_creates_new_active(db: Session, factory) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.submitted_at = datetime.now(tz=UTC)
    app.locked_after_submit = True
    app.current_stage = ApplicationStage.initial_screening.value
    db.flush()
    commission_repository.upsert_projection_for_application(db, app)
    db.flush()

    old_id = app.id
    out = commission_service.archive_application_by_commission(
        db,
        application_id=old_id,
        actor_user_id=user.id,
        reason="unit test",
    )
    db.flush()

    assert out["archived_application_id"] == old_id
    new_app = get_application_for_candidate(db, profile.id)
    assert new_app is not None
    assert new_app.id == out["new_application_id"]
    assert new_app.is_archived is False
    assert new_app.state == ApplicationState.draft.value
    assert new_app.current_stage == ApplicationStage.application.value

    active_rows = commission_repository.list_projections(db, limit=200)
    assert all(r.application_id != old_id for r in active_rows)

    archived_rows = commission_repository.list_archived_projections(db, limit=200)
    assert any(r.application_id == old_id for r in archived_rows)


def test_archive_twice_returns_409(db: Session, factory) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.submitted_at = datetime.now(tz=UTC)
    app.locked_after_submit = True
    db.flush()
    commission_repository.upsert_projection_for_application(db, app)
    db.flush()

    commission_service.archive_application_by_commission(
        db, application_id=app.id, actor_user_id=user.id, reason=None
    )
    db.flush()

    with pytest.raises(HTTPException) as exc_info:
        commission_service.archive_application_by_commission(
            db, application_id=app.id, actor_user_id=user.id, reason=None
        )
    assert exc_info.value.status_code == 409
