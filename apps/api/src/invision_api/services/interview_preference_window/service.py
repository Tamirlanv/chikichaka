"""1-hour window for candidate preferred interview slots; expiry sweep; close on commission schedule."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.commission.application.service import rebuild_projection
from invision_api.models.application import Application, InterviewSession
from invision_api.models.enums import ApplicationStage, InterviewPreferenceWindowStatus
from invision_api.repositories import admissions_repository
from invision_api.services import audit_log_service

logger = logging.getLogger(__name__)

PREFERENCE_WINDOW = timedelta(hours=1)
COMMISSION_INTERVIEW_SESSION_INDEX = 0


def has_scheduled_commission_interview(db: Session, application_id: UUID) -> bool:
    row = db.scalars(
        select(InterviewSession.id).where(
            InterviewSession.application_id == application_id,
            InterviewSession.scheduled_at.is_not(None),
        )
    ).first()
    return row is not None


def get_commission_interview_session(db: Session, application_id: UUID) -> InterviewSession | None:
    """Latest session for commission slot index (deterministic if legacy duplicates exist)."""
    return db.scalars(
        select(InterviewSession)
        .where(
            InterviewSession.application_id == application_id,
            InterviewSession.session_index == COMMISSION_INTERVIEW_SESSION_INDEX,
        )
        .order_by(InterviewSession.created_at.desc())
        .limit(1)
    ).first()


def _set_window_status(db: Session, app: Application, status: InterviewPreferenceWindowStatus) -> None:
    app.interview_preference_window_status = status.value
    db.flush()


def close_window_on_commission_schedule(db: Session, app: Application) -> None:
    app.interview_preference_window_status = InterviewPreferenceWindowStatus.interview_scheduled.value
    now = datetime.now(tz=UTC)
    if app.interview_preference_window_expires_at is None:
        app.interview_preference_window_opened_at = now
        app.interview_preference_window_expires_at = now
    db.flush()


def ensure_preference_window_expired_for_application(db: Session, application_id: UUID) -> bool:
    """If window expired and still awaiting, mark expired. Returns True if state changed."""
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        return False
    if app.interview_preference_window_status != InterviewPreferenceWindowStatus.awaiting_candidate_preferences.value:
        return False
    if has_scheduled_commission_interview(db, application_id):
        close_window_on_commission_schedule(db, app)
        rebuild_projection(db, application_id)
        return True
    exp = app.interview_preference_window_expires_at
    if not exp or exp > datetime.now(tz=UTC):
        return False
    app.interview_preference_window_status = InterviewPreferenceWindowStatus.candidate_preferences_expired.value
    db.flush()
    rebuild_projection(db, application_id)
    audit_log_service.write_audit(
        db,
        entity_type="application",
        entity_id=application_id,
        action="interview_preference_window_expired",
        actor_user_id=None,
        after_data={"expiresAt": exp.isoformat()},
    )
    logger.info("interview_preference_window_expired application_id=%s", application_id)
    return True


def open_preference_window_on_ai_complete(db: Session, app: Application) -> None:
    """Call after AI interview is marked complete. Idempotent; does not override interview_scheduled."""
    if app.current_stage != ApplicationStage.interview.value:
        return
    ensure_preference_window_expired_for_application(db, app.id)
    db.refresh(app)
    if has_scheduled_commission_interview(db, app.id):
        _set_window_status(db, app, InterviewPreferenceWindowStatus.interview_scheduled)
        return
    st = app.interview_preference_window_status
    if st == InterviewPreferenceWindowStatus.interview_scheduled.value:
        return
    if app.interview_preferences_submitted_at is not None:
        if st != InterviewPreferenceWindowStatus.candidate_preferences_submitted.value:
            _set_window_status(db, app, InterviewPreferenceWindowStatus.candidate_preferences_submitted)
        return
    if st in (
        InterviewPreferenceWindowStatus.candidate_preferences_submitted.value,
        InterviewPreferenceWindowStatus.candidate_preferences_expired.value,
    ):
        return
    now = datetime.now(tz=UTC)
    if st == InterviewPreferenceWindowStatus.awaiting_candidate_preferences.value:
        return

    app.interview_preference_window_opened_at = now
    app.interview_preference_window_expires_at = now + PREFERENCE_WINDOW
    app.interview_preference_window_status = InterviewPreferenceWindowStatus.awaiting_candidate_preferences.value
    db.flush()


def mark_preferences_submitted(db: Session, app: Application) -> None:
    app.interview_preference_window_status = InterviewPreferenceWindowStatus.candidate_preferences_submitted.value
    db.flush()


def sweep_expired_preference_windows(db: Session, *, limit: int = 500) -> int:
    """Mark awaiting windows past expiry. Returns count updated."""
    now = datetime.now(tz=UTC)
    rows = db.scalars(
        select(Application)
        .where(
            Application.current_stage == ApplicationStage.interview.value,
            Application.interview_preference_window_status
            == InterviewPreferenceWindowStatus.awaiting_candidate_preferences.value,
            Application.interview_preference_window_expires_at.is_not(None),
            Application.interview_preference_window_expires_at < now,
        )
        .limit(limit)
    ).all()
    n = 0
    for app in rows:
        if has_scheduled_commission_interview(db, app.id):
            close_window_on_commission_schedule(db, app)
            rebuild_projection(db, app.id)
            n += 1
            continue
        if ensure_preference_window_expired_for_application(db, app.id):
            n += 1
    return n


def build_preference_window_payload_for_candidate(db: Session, app: Application) -> dict[str, Any]:
    """Ensure lazy expiry then return window fields for API."""
    ensure_preference_window_expired_for_application(db, app.id)
    db.refresh(app)
    status = app.interview_preference_window_status
    opened = app.interview_preference_window_opened_at
    expires = app.interview_preference_window_expires_at
    remaining: int | None = None
    if (
        status == InterviewPreferenceWindowStatus.awaiting_candidate_preferences.value
        and expires is not None
    ):
        delta = expires - datetime.now(tz=UTC)
        remaining = max(0, int(delta.total_seconds()))
    return {
        "openedAt": opened.isoformat() if opened else None,
        "expiresAt": expires.isoformat() if expires else None,
        "status": status,
        "remainingSeconds": remaining,
    }
