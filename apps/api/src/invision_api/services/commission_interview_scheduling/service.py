"""Commission assigns final commission interview time (InterviewSession); closes preference window."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from invision_api.commission.application.service import rebuild_projection
from invision_api.models.application import InterviewSession
from invision_api.models.enums import ApplicationStage
from invision_api.repositories import admissions_repository
from invision_api.services import audit_log_service
from invision_api.services.interview_preference_window.service import (
    COMMISSION_INTERVIEW_SESSION_INDEX,
    close_window_on_commission_schedule,
    get_commission_interview_session,
)

logger = logging.getLogger(__name__)


def upsert_commission_interview_schedule(
    db: Session,
    application_id: UUID,
    *,
    scheduled_at: datetime,
    interview_mode: str | None,
    location_or_link: str | None,
    scheduled_by_user_id: UUID,
) -> InterviewSession:
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if app.current_stage != ApplicationStage.interview.value:
        raise HTTPException(status_code=409, detail="Назначение доступно на этапе собеседования.")

    sess = get_commission_interview_session(db, application_id)
    if sess:
        sess.scheduled_at = scheduled_at
        sess.interview_mode = (interview_mode or "").strip() or None
        sess.location_or_link = (location_or_link or "").strip() or None
        sess.scheduled_by_user_id = scheduled_by_user_id
        sess.interview_status = "scheduled"
        db.flush()
        row = sess
    else:
        row = admissions_repository.create_interview_session(
            db,
            application_id,
            session_index=COMMISSION_INTERVIEW_SESSION_INDEX,
            interview_status="scheduled",
            scheduled_at=scheduled_at,
            scheduled_by_user_id=scheduled_by_user_id,
            interview_mode=(interview_mode or "").strip() or None,
            location_or_link=(location_or_link or "").strip() or None,
        )
        db.flush()

    close_window_on_commission_schedule(db, app)
    rebuild_projection(db, application_id)
    audit_log_service.write_audit(
        db,
        entity_type="application",
        entity_id=application_id,
        action="commission_interview_scheduled",
        actor_user_id=scheduled_by_user_id,
        after_data={
            "session_id": str(row.id),
            "scheduled_at": scheduled_at.isoformat(),
            "interview_mode": row.interview_mode,
        },
    )
    logger.info(
        "commission_interview_scheduled application_id=%s session_id=%s",
        application_id,
        row.id,
    )
    return row


def interview_session_to_api_dict(sess: InterviewSession) -> dict[str, Any]:
    return {
        "sessionId": str(sess.id),
        "scheduledAt": sess.scheduled_at.isoformat() if sess.scheduled_at else None,
        "interviewMode": sess.interview_mode,
        "locationOrLink": sess.location_or_link,
        "scheduledByUserId": str(sess.scheduled_by_user_id) if sess.scheduled_by_user_id else None,
        "reminderRequestedAt": sess.reminder_requested_at.isoformat() if sess.reminder_requested_at else None,
        "reminderSentAt": sess.reminder_sent_at.isoformat() if sess.reminder_sent_at else None,
        "outcomeRecordedAt": sess.outcome_recorded_at.isoformat() if sess.outcome_recorded_at else None,
    }


def record_commission_interview_outcome(
    db: Session,
    application_id: UUID,
    *,
    actor_user_id: UUID,
) -> InterviewSession:
    """Mark that commission recorded the outcome of the scheduled live interview (Kanban guard)."""
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if app.current_stage != ApplicationStage.interview.value:
        raise HTTPException(status_code=409, detail="Подтверждение доступно на этапе собеседования.")

    sess = get_commission_interview_session(db, application_id)
    if not sess or sess.scheduled_at is None:
        raise HTTPException(status_code=409, detail="Сначала назначьте собеседование с комиссией.")
    now = datetime.now(tz=UTC)
    if sess.scheduled_at > now:
        raise HTTPException(status_code=409, detail="Дата собеседования ещё не наступила.")

    if sess.outcome_recorded_at is not None:
        return sess

    sess.outcome_recorded_at = now
    db.flush()
    rebuild_projection(db, application_id)
    audit_log_service.write_audit(
        db,
        entity_type="application",
        entity_id=application_id,
        action="commission_interview_outcome_recorded",
        actor_user_id=actor_user_id,
        after_data={"session_id": str(sess.id), "outcome_recorded_at": now.isoformat()},
    )
    logger.info(
        "commission_interview_outcome_recorded application_id=%s session_id=%s",
        application_id,
        sess.id,
    )
    return sess
