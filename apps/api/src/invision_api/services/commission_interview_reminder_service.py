"""Candidate requests email reminder 3 hours before commission interview."""

from __future__ import annotations

import html
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import Application, CandidateProfile, InterviewSession
from invision_api.services import candidate_activity_service
from invision_api.services.candidate_stage_email_service import _load_candidate_email_and_name
from invision_api.services.email_delivery import send_html_email
from invision_api.services.interview_preference_window.service import get_commission_interview_session

logger = logging.getLogger(__name__)

REMINDER_LEAD = timedelta(hours=3)  # email goes out at T−3h (or immediately if already in window)


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _try_send_reminder_email(db: Session, sess: InterviewSession, *, now: datetime) -> bool:
    """Send if in [T-3h, T). Returns True if email was sent."""
    if sess.reminder_sent_at or not sess.scheduled_at or not sess.reminder_requested_at:
        return False
    start = _aware(sess.scheduled_at)
    if now >= start:
        return False
    window_open = start - REMINDER_LEAD
    if now < window_open:
        return False
    to_email, first = _load_candidate_email_and_name(db, sess.application_id)
    if not to_email:
        logger.warning("commission_interview_reminder: no email application_id=%s", sess.application_id)
        return False
    name = html.escape((first or "Кандидат").strip())
    when = html.escape(start.isoformat(timespec="minutes"))
    mode = html.escape((sess.interview_mode or "").strip() or "—")
    link = (sess.location_or_link or "").strip()
    link_html = (
        f'<a href="{html.escape(link)}">{html.escape(link)}</a>'
        if link.startswith("http")
        else html.escape(link or "—")
    )
    subject = "Напоминание: собеседование с комиссией inVision U"
    body = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
<p>Здравствуйте, {name}!</p>
<p>Напоминаем, что через 3 часа у вас собеседование с комиссией.</p>
<p><strong>Когда:</strong> {when}<br/>
<strong>Платформа / формат:</strong> {mode}<br/>
<strong>Ссылка или адрес:</strong> {link_html}</p>
<p>С уважением,<br/>команда inVision U</p>
</body></html>"""
    if send_html_email(to_email, subject, body):
        sess.reminder_sent_at = now
        return True
    return False


def sweep_commission_interview_reminders(db: Session) -> int:
    """Send due reminders (worker idle sweep). Returns count sent."""
    now = datetime.now(tz=UTC)
    rows = list(
        db.scalars(
            select(InterviewSession).where(
                InterviewSession.scheduled_at.is_not(None),
                InterviewSession.reminder_requested_at.is_not(None),
                InterviewSession.reminder_sent_at.is_(None),
            )
        ).all()
    )
    n = 0
    for sess in rows:
        if _try_send_reminder_email(db, sess, now=now):
            n += 1
    if n:
        db.commit()
    return n


def request_commission_interview_reminder(db: Session, application_id: UUID) -> dict[str, Any]:
    sess = get_commission_interview_session(db, application_id)
    if not sess or not sess.scheduled_at:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Собеседование с комиссией ещё не назначено.",
        )
    now = datetime.now(tz=UTC)
    if sess.reminder_sent_at:
        return {"ok": True, "alreadySent": True}
    if sess.reminder_requested_at:
        return {"ok": True, "alreadyRequested": True}
    sess.reminder_requested_at = now
    app_row = db.execute(
        select(CandidateProfile.user_id, Application.current_stage)
        .select_from(Application)
        .join(CandidateProfile, CandidateProfile.id == Application.candidate_profile_id)
        .where(Application.id == application_id)
        .limit(1)
    ).first()
    if app_row is not None:
        actor_uid, current_stage = app_row
        candidate_activity_service.record_candidate_activity_event(
            db,
            application_id=application_id,
            candidate_user_id=actor_uid,
            event_type="reminder_requested",
            occurred_at=now,
            stage=current_stage,
        )
    db.flush()
    _try_send_reminder_email(db, sess, now=now)
    db.commit()
    db.refresh(sess)
    return {"ok": True, "reminderSent": bool(sess.reminder_sent_at)}
