"""Interview scheduling and notes."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.application import Application
from invision_api.models.enums import ApplicationStage
from invision_api.repositories import admissions_repository
from invision_api.services.stage_transition_policy import TransitionContext, TransitionName, apply_transition


def schedule_session(
    db: Session,
    application_id: UUID,
    *,
    session_index: int,
    scheduled_at: datetime | None,
    interview_mode: str | None,
    location_or_link: str | None,
    scheduled_by_user_id: UUID | None = None,
) -> Any:
    return admissions_repository.create_interview_session(
        db,
        application_id,
        session_index=session_index,
        interview_status="scheduled",
        scheduled_at=scheduled_at,
        scheduled_by_user_id=scheduled_by_user_id,
        interview_mode=interview_mode,
        location_or_link=location_or_link,
    )


def complete_interview_stage(
    db: Session,
    app: Application,
    *,
    actor_user_id: UUID | None,
) -> Application:
    if app.current_stage != ApplicationStage.interview.value:
        raise ValueError("application must be in interview stage")
    ctx = TransitionContext(
        application_id=app.id,
        transition=TransitionName.interview_complete,
        actor_user_id=actor_user_id,
        actor_type="committee",
    )
    return apply_transition(db, app, ctx)
