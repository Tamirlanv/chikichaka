"""Candidate interview time preferences: weekday slots 09–17, global uniqueness per (date, slot code)."""

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
from invision_api.services import audit_log_service

logger = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Moscow")

# Non-overlapping codes within 09:00–17:00
CANONICAL_SLOTS: list[tuple[str, str]] = [
    ("09-11", "09:00–11:00"),
    ("11-13", "11:00–13:00"),
    ("13-15", "13:00–15:00"),
    ("15-17", "15:00–17:00"),
]

SLOT_CODES_ORDER = [c for c, _ in CANONICAL_SLOTS]
SLOT_LABEL_BY_CODE = dict(CANONICAL_SLOTS)


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


def _booked_codes_for_date(db: Session, slot_d: date) -> set[str]:
    rows = db.scalars(
        select(InterviewSlotBooking.time_range_code).where(InterviewSlotBooking.slot_date == slot_d)
    ).all()
    return set(rows)


def list_available_days(db: Session, application_id: UUID) -> dict[str, Any]:
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if app.current_stage != ApplicationStage.interview.value:
        raise HTTPException(status_code=409, detail="Доступно на этапе собеседования.")
    _require_ai_interview_completed_for_preferences(db, application_id)

    start = _today_moscow() + timedelta(days=1)
    end = start + timedelta(days=60)
    days_out: list[dict[str, Any]] = []
    for d in _weekday_dates(start, end):
        booked = _booked_codes_for_date(db, d)
        free_any = any(code not in booked for code in SLOT_CODES_ORDER)
        if not free_any:
            continue
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

    if slot_date.weekday() >= 5:
        return {"slots": []}

    booked = _booked_codes_for_date(db, slot_date)
    slots: list[dict[str, str]] = []
    for code, label in CANONICAL_SLOTS:
        if code not in booked:
            slots.append({"timeRangeCode": code, "label": label})
    return {"slots": slots}


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
    if app.interview_preferences_submitted_at is not None:
        raise HTTPException(status_code=409, detail="Предпочтения уже отправлены.")

    _require_ai_interview_completed_for_preferences(db, application_id)

    if not slots or len(slots) > 3:
        raise HTTPException(status_code=422, detail="Укажите от 1 до 3 вариантов времени.")

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
        if d.weekday() >= 5:
            raise HTTPException(status_code=422, detail="Выходные дни недоступны.")
        if code not in SLOT_LABEL_BY_CODE:
            raise HTTPException(status_code=422, detail="Некорректный интервал времени.")
        key = (ds[:10], code)
        if key in seen_pairs:
            raise HTTPException(status_code=422, detail="Нельзя выбрать один и тот же слот дважды.")
        seen_pairs.add(key)
        normalized.append((d, code, i + 1))

    # Final availability check
    for d, code, _ in normalized:
        booked = _booked_codes_for_date(db, d)
        if code in booked:
            logger.warning(
                "interview_preferences_slot_taken application_id=%s date=%s code=%s",
                application_id,
                d.isoformat(),
                code,
            )
            raise HTTPException(
                status_code=409,
                detail=f"Слот {SLOT_LABEL_BY_CODE.get(code, code)} на {d.isoformat()} уже занят. Выберите другой вариант.",
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
            detail="Один из выбранных слотов уже занят. Обновите список и выберите другой вариант.",
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
    logger.info(
        "interview_preferences_submitted application_id=%s slot_count=%s",
        application_id,
        len(normalized),
    )

    return {"ok": True, "submittedAt": now.isoformat()}
