"""Candidate interview time preferences: 1-hour weekday slots 09:00–17:00; preferences only (no global booking)."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from invision_api.commission.application.service import rebuild_projection
from invision_api.models.application import CandidateProfile
from invision_api.models.commission import InterviewSlotBooking
from invision_api.models.enums import ApplicationStage
from invision_api.repositories import admissions_repository, ai_interview_repository
from invision_api.services import audit_log_service, candidate_activity_service
from invision_api.services.interview_preference_window.service import (
    ensure_preference_window_expired_for_application,
    has_scheduled_commission_interview,
    mark_preferences_submitted,
)

logger = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Moscow")

# One-hour bands, working day 09:00–17:00 (last slot 16:00–17:00).
CANONICAL_SLOTS: list[tuple[str, str]] = [
    ("09-10", "09:00–10:00"),
    ("10-11", "10:00–11:00"),
    ("11-12", "11:00–12:00"),
    ("12-13", "12:00–13:00"),
    ("13-14", "13:00–14:00"),
    ("14-15", "14:00–15:00"),
    ("15-16", "15:00–16:00"),
    ("16-17", "16:00–17:00"),
]

# Legacy 2h codes (display only for rows saved before 1h slots).
_LEGACY_SLOT_LABELS: dict[str, str] = {
    "09-11": "09:00–11:00",
    "11-13": "11:00–13:00",
    "13-15": "13:00–15:00",
    "15-17": "15:00–17:00",
}

SLOT_LABEL_BY_CODE = {**dict(CANONICAL_SLOTS), **_LEGACY_SLOT_LABELS}


def _require_ai_interview_completed_for_preferences(db: Session, application_id: UUID) -> None:
    """Preferences API only after commission-approved questions and candidate-completed AI session."""
    qs = ai_interview_repository.get_question_set_for_application(db, application_id)
    if not qs or qs.status != "approved":
        raise HTTPException(
            status_code=409,
            detail="Вопросы AI-собеседования ещё не утверждены. Выбор времени недоступен.",
        )
    if qs.candidate_completed_at is None:
        raise HTTPException(
            status_code=409,
            detail="Сначала завершите AI-собеседование.",
        )


def _today_moscow() -> date:
    return datetime.now(tz=TZ).date()


def _weekday_dates(start: date, end: date) -> list[date]:
    out: list[date] = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def list_available_days(db: Session, application_id: UUID) -> dict[str, Any]:
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if app.current_stage != ApplicationStage.interview.value:
        raise HTTPException(status_code=409, detail="Доступно на этапе собеседования.")
    _require_ai_interview_completed_for_preferences(db, application_id)
    if has_scheduled_commission_interview(db, application_id):
        raise HTTPException(status_code=409, detail="Собеседование с комиссией уже назначено.")

    start = _today_moscow() + timedelta(days=1)
    end = start + timedelta(days=60)
    days_out: list[dict[str, Any]] = []
    for d in _weekday_dates(start, end):
        days_out.append(
            {
                "date": d.isoformat(),
                "label": _format_day_label(d),
            }
        )
    return {"days": days_out}


def _format_day_label(d: date) -> str:
    dt = datetime(d.year, d.month, d.day, tzinfo=TZ)
    wd = ("понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье")[d.weekday()]
    month_names = (
        "января",
        "февраля",
        "марта",
        "апреля",
        "мая",
        "июня",
        "июля",
        "августа",
        "сентября",
        "октября",
        "ноября",
        "декабря",
    )
    return f"{d.day} {month_names[d.month - 1]}, {wd}"


def list_available_slots_for_date(db: Session, application_id: UUID, slot_date: date) -> dict[str, Any]:
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if app.current_stage != ApplicationStage.interview.value:
        raise HTTPException(status_code=409, detail="Доступно на этапе собеседования.")
    _require_ai_interview_completed_for_preferences(db, application_id)
    if has_scheduled_commission_interview(db, application_id):
        raise HTTPException(status_code=409, detail="Собеседование с комиссией уже назначено.")

    if slot_date.weekday() >= 5:
        return {"slots": []}

    slots: list[dict[str, str]] = []
    for code, label in CANONICAL_SLOTS:
        slots.append({"timeRangeCode": code, "label": label})
    return {"slots": slots}


def _slot_date_allowed_range() -> tuple[date, date]:
    """Same calendar window as list_available_days (Moscow)."""
    start = _today_moscow() + timedelta(days=1)
    end = start + timedelta(days=60)
    return start, end


def submit_interview_preferences(
    db: Session,
    application_id: UUID,
    *,
    slots: list[dict[str, Any]],
) -> dict[str, Any]:
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if app.current_stage != ApplicationStage.interview.value:
        raise HTTPException(status_code=409, detail="Доступно на этапе собеседования.")
    ensure_preference_window_expired_for_application(db, application_id)
    db.refresh(app)
    if has_scheduled_commission_interview(db, application_id):
        raise HTTPException(status_code=409, detail="Собеседование с комиссией уже назначено.")
    if app.interview_preferences_submitted_at is not None:
        raise HTTPException(status_code=409, detail="Предпочтения уже отправлены.")

    _require_ai_interview_completed_for_preferences(db, application_id)

    if not slots or len(slots) > 3:
        raise HTTPException(status_code=422, detail="Укажите от 1 до 3 вариантов времени.")

    date_min, date_max = _slot_date_allowed_range()
    normalized: list[tuple[date, str, int]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for i, raw in enumerate(slots):
        ds = str(raw.get("date") or raw.get("slotDate") or "").strip()
        code = str(raw.get("timeRangeCode") or raw.get("time_range_code") or "").strip()
        if not ds or not code:
            raise HTTPException(status_code=422, detail="Каждый вариант должен содержать дату и интервал времени.")
        try:
            d = date.fromisoformat(ds[:10])
        except ValueError as e:
            raise HTTPException(status_code=422, detail="Некорректная дата.") from e
        if d < date_min or d > date_max:
            raise HTTPException(status_code=422, detail="Дата вне доступного диапазона для предпочтений.")
        if d.weekday() >= 5:
            raise HTTPException(status_code=422, detail="Выходные дни недоступны.")
        if code not in SLOT_LABEL_BY_CODE:
            raise HTTPException(status_code=422, detail="Некорректный интервал времени.")
        key = (ds[:10], code)
        if key in seen_pairs:
            raise HTTPException(status_code=422, detail="Нельзя выбрать один и тот же слот дважды.")
        seen_pairs.add(key)
        normalized.append((d, code, i + 1))

    if has_scheduled_commission_interview(db, application_id):
        raise HTTPException(
            status_code=409,
            detail="Собеседование с комиссией уже назначено. Обновите страницу.",
        )

    now = datetime.now(tz=UTC)
    db.execute(delete(InterviewSlotBooking).where(InterviewSlotBooking.application_id == application_id))
    for d, code, sort_order in normalized:
        db.add(
            InterviewSlotBooking(
                application_id=application_id,
                slot_date=d,
                time_range_code=code,
                sort_order=sort_order,
            )
        )
    app.interview_preferences_submitted_at = now
    mark_preferences_submitted(db, app)
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        logger.warning(
            "interview_preferences_integrity_collision application_id=%s",
            application_id,
        )
        raise HTTPException(
            status_code=409,
            detail="Не удалось сохранить предпочтения. Обновите страницу и попробуйте снова.",
        ) from e
    rebuild_projection(db, application_id)

    prof = db.get(CandidateProfile, app.candidate_profile_id)
    actor_uid = prof.user_id if prof else None
    audit_log_service.write_audit(
        db,
        entity_type="application",
        entity_id=application_id,
        action="candidate_interview_preferences_submitted",
        actor_user_id=actor_uid,
        after_data={"slot_count": len(normalized), "submitted_at": now.isoformat()},
    )
    if actor_uid is not None:
        candidate_activity_service.record_candidate_activity_event(
            db,
            application_id=application_id,
            candidate_user_id=actor_uid,
            event_type="interview_preferences_submitted",
            occurred_at=now,
            stage=app.current_stage,
            metadata={"slotCount": len(normalized)},
        )
    logger.info(
        "interview_preferences_submitted application_id=%s slot_count=%s",
        application_id,
        len(normalized),
    )

    return {"ok": True, "submittedAt": now.isoformat()}
