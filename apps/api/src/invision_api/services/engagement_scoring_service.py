from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from invision_api.commission.domain.mapping import application_to_commission_column
from invision_api.models.ai_interview import AIInterviewAnswer
from invision_api.models.application import (
    Application,
    ApplicationSectionState,
    AuditLog,
    CandidateProfile,
    Document,
    InternalTestAnswer,
    InterviewSession,
)
from invision_api.models.candidate_activity_event import CandidateActivityEvent
from invision_api.models.enums import ApplicationStage
from invision_api.repositories import commission_repository


ACTIVE_COMMISSION_COLUMNS = {"data_check", "application_review", "interview", "committee_decision"}
INTERVIEW_STAGES = {
    ApplicationStage.interview.value,
    ApplicationStage.committee_review.value,
    ApplicationStage.decision.value,
}
CANDIDATE_ACTION_STAGES = {
    ApplicationStage.application.value,
    ApplicationStage.interview.value,
}

ENGAGEMENT_RANK = {"Low": 0, "Medium": 1, "High": 2}
RISK_RANK = {"Low": 0, "Medium": 1, "High": 2}


def _hours_word_ru(n: int) -> str:
    n10 = n % 10
    n100 = n % 100
    if n10 == 1 and n100 != 11:
        return "час"
    if 2 <= n10 <= 4 and n100 not in (12, 13, 14):
        return "часа"
    return "часов"


def _days_word_ru(n: int) -> str:
    n10 = n % 10
    n100 = n % 100
    if n10 == 1 and n100 != 11:
        return "день"
    if 2 <= n10 <= 4 and n100 not in (12, 13, 14):
        return "дня"
    return "дней"


def _minutes_word_ru(n: int) -> str:
    n10 = n % 10
    n100 = n % 100
    if n10 == 1 and n100 != 11:
        return "минута"
    if 2 <= n10 <= 4 and n100 not in (12, 13, 14):
        return "минуты"
    return "минут"


def _format_active_time_humanized(total_minutes: int) -> str:
    minutes = max(int(total_minutes), 0)
    hours = minutes // 60
    mins = minutes % 60
    if hours <= 0:
        return f"{mins} {_minutes_word_ru(mins)}"
    return f"{hours} {_hours_word_ru(hours)} {mins} {_minutes_word_ru(mins)}"


def humanize_last_activity(last_activity_at: datetime | None, *, now: datetime | None = None) -> str:
    if last_activity_at is None:
        return "нет активности"
    current = now or datetime.now(tz=UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    dt = last_activity_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    if dt > current:
        dt = current
    delta = current - dt
    minutes = max(int(delta.total_seconds() // 60), 0)
    if minutes < 60:
        return "только что"
    hours = minutes // 60
    if hours < 24:
        if hours == 1:
            return "1 час назад"
        return f"{hours} {_hours_word_ru(hours)} назад"
    days = delta.days
    if days == 1:
        return "1 день назад"
    if days < 7:
        return f"{days} {_days_word_ru(days)} назад"
    if days < 14:
        return "неделю назад"
    if days < 21:
        return "2 недели назад"
    if days < 45:
        return "месяц назад"
    months = max(days // 30, 2)
    return f"{months} мес. назад"


def _time_to_submit_bucket(submitted_at: datetime | None, registered_at: datetime | None) -> str:
    if submitted_at is None or registered_at is None:
        return "unknown"
    delta = submitted_at - registered_at
    minutes = delta.total_seconds() / 60.0
    if minutes <= 30:
        return "poor"
    if minutes < 180:
        return "medium"
    if minutes <= 24 * 60:
        return "good"
    return "medium"


def _last_online_bucket(last_activity_at: datetime | None, *, now: datetime) -> str:
    if last_activity_at is None:
        return "poor"
    delta = now - last_activity_at
    if delta <= timedelta(days=1):
        return "good"
    if delta < timedelta(days=5):
        return "medium"
    return "poor"


def _active_time_bucket(unique_minutes: int) -> str:
    if unique_minutes >= 45:
        return "good"
    if unique_minutes >= 15:
        return "medium"
    return "poor"


def _resolve_speed_signal(submitted_at: datetime | None, registered_at: datetime | None) -> tuple[str, bool]:
    if submitted_at is None or registered_at is None:
        return ("нет данных", False)
    delta_minutes = (submitted_at - registered_at).total_seconds() / 60.0
    if delta_minutes <= 30:
        return ("слишком быстро", False)
    if delta_minutes < 180:
        return ("умеренно быстро", False)
    if delta_minutes <= 24 * 60:
        return ("быстро", False)
    return ("умеренно быстро", True)


def _sort_cards(cards: list[dict[str, Any]], *, sort: str) -> list[dict[str, Any]]:
    if sort == "freshness":
        return sorted(
            cards,
            key=lambda x: (
                x.get("lastActivityAtIso") is not None,
                x.get("lastActivityAtIso") or "",
                x.get("candidateFullName") or "",
            ),
            reverse=True,
        )
    if sort == "engagement":
        return sorted(
            cards,
            key=lambda x: (
                ENGAGEMENT_RANK.get(str(x.get("engagementLevel")), -1),
                x.get("lastActivityAtIso") or "",
                x.get("candidateFullName") or "",
            ),
            reverse=True,
        )
    # default: stale first
    return sorted(
        cards,
        key=lambda x: (
            x.get("lastActivityAtIso") is not None,
            x.get("lastActivityAtIso") or "",
            x.get("candidateFullName") or "",
        ),
    )


def _current_stage_entered_at(app: Application) -> datetime | None:
    open_rows = [h for h in app.stage_history if h.exited_at is None and h.to_stage == app.current_stage]
    if open_rows:
        return max(open_rows, key=lambda h: h.entered_at).entered_at
    same_stage = [h for h in app.stage_history if h.to_stage == app.current_stage]
    if same_stage:
        return max(same_stage, key=lambda h: h.entered_at).entered_at
    return None


def _first_interview_stage_entered_at(app: Application | None) -> datetime | None:
    if not app:
        return None
    rows = [h.entered_at for h in app.stage_history if h.to_stage == ApplicationStage.interview.value]
    return min(rows) if rows else None


def _section_payload(app: Application | None, section_key: str) -> dict[str, Any]:
    if not app:
        return {}
    for row in app.section_states:
        if row.section_key == section_key and isinstance(row.payload, dict):
            return row.payload
    return {}


def _build_interpretation_lines(
    *,
    engagement_level: str,
    risk_level: str,
    speed_label: str,
    speed_delay: bool,
    stage_start_response_bucket: str,
    stage_stagnation_bucket: str,
    reminder_response_bucket: str,
) -> list[str]:
    lines: list[str] = []
    if engagement_level == "High" and risk_level == "Low":
        lines.append("Есть признаки устойчивого интереса и последовательного участия в процессе.")
    elif engagement_level == "Medium":
        lines.append("Вовлечённость выглядит умеренной: есть рабочая активность, но неравномерный темп действий.")
    else:
        lines.append("Вовлечённость снижена: заметны паузы и слабая динамика по текущему этапу.")

    if speed_label == "слишком быстро":
        lines.append("Подача выглядит слишком быстрой, поэтому глубину проработки анкеты стоит интерпретировать осторожно.")
    elif speed_delay:
        lines.append("Часть действий выполнялась с задержками, это снижает предсказуемость дальнейшего участия.")

    if stage_start_response_bucket == "quick_start":
        lines.append("Реакция на следующий этап своевременная.")
    elif stage_start_response_bucket == "no_start" or stage_stagnation_bucket in {"mild", "severe"}:
        lines.append("Есть задержки в старте действий на новом этапе.")

    if reminder_response_bucket == "ignored":
        lines.append("На напоминания платформа получала слабый отклик.")
    elif reminder_response_bucket == "reacted_fast":
        lines.append("Кандидат оперативно реагирует на напоминания платформы.")

    deduped: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if line not in seen:
            deduped.append(line)
            seen.add(line)
    return deduped[:4] if deduped else ["Недостаточно данных для уверенной интерпретации вовлечённости."]


def _build_final_line(
    *,
    engagement_level: str,
    risk_level: str,
    speed_label: str,
    speed_delay: bool,
    submitted_done: bool,
) -> str:
    if speed_label == "слишком быстро":
        return (
            "Подача выглядит слишком быстрой, поэтому глубину вовлечённости стоит оценивать аккуратно и уточнить "
            "мотивацию на собеседовании."
        )
    if engagement_level == "High" and risk_level == "Low" and submitted_done:
        return "Кандидат выглядит стабильно вовлечённым: участие в процессе последовательное, реакция на этапы своевременная."
    if risk_level == "High":
        return "Интерес к процессу есть, но выражены риски выпадения: комиссии стоит усилить сопровождение кандидата."
    if speed_delay:
        return "Вовлечённость скорее умеренная: участие осознанное, но часть действий выполнялась с задержками."
    return "Кандидат демонстрирует рабочую вовлечённость, но по темпу и стабильности участия есть зоны для внимания."


def _compute_engagement_insight(
    *,
    app: Application | None,
    registered_at: datetime | None,
    candidate_user_id: UUID | None,
    events: list[CandidateActivityEvent],
    audits: list[AuditLog],
    docs: list[Document],
    test_answers: list[InternalTestAnswer],
    ai_answers: list[AIInterviewAnswer],
    now: datetime,
) -> dict[str, Any]:
    timestamps: list[datetime] = []
    for ev in events:
        if ev.occurred_at is not None:
            timestamps.append(ev.occurred_at)
    if app and app.submitted_at:
        timestamps.append(app.submitted_at)
    if app and app.interview_preferences_submitted_at:
        timestamps.append(app.interview_preferences_submitted_at)
    for ss in app.section_states if app else []:
        if isinstance(ss, ApplicationSectionState) and ss.last_saved_at is not None:
            timestamps.append(ss.last_saved_at)
    for d in docs:
        if candidate_user_id is None or d.uploaded_by_user_id == candidate_user_id:
            if d.created_at is not None:
                timestamps.append(d.created_at)
    for t in test_answers:
        if t.saved_at is not None:
            timestamps.append(t.saved_at)
        if t.submitted_at:
            timestamps.append(t.submitted_at)
    for a in ai_answers:
        if a.updated_at is not None:
            timestamps.append(a.updated_at)
    for aud in audits:
        if candidate_user_id is not None and aud.actor_user_id == candidate_user_id and aud.created_at is not None:
            timestamps.append(aud.created_at)

    last_activity_at = max(timestamps) if timestamps else registered_at
    last_activity_humanized = humanize_last_activity(last_activity_at, now=now)

    time_to_submit_bucket = _time_to_submit_bucket(app.submitted_at if app else None, registered_at)
    last_online_bucket = _last_online_bucket(last_activity_at, now=now)
    speed_label, speed_delay = _resolve_speed_signal(app.submitted_at if app else None, registered_at)

    active_minutes: set[datetime] = set()
    for ev in events:
        if ev.event_type == "platform_interaction_ping" or ev.event_type in {
            "stage_action_started",
            "interview_info_opened",
            "interview_instruction_opened",
            "interview_link_copied",
            "interview_link_opened",
            "section_saved",
            "document_uploaded",
            "internal_test_saved",
            "internal_test_submitted",
            "application_submitted",
            "application_reopened",
            "interview_preferences_submitted",
            "ai_interview_completed",
            "reminder_requested",
        }:
            active_minutes.add(ev.occurred_at.replace(second=0, microsecond=0))
    for ts in timestamps:
        if ts is not None:
            active_minutes.add(ts.replace(second=0, microsecond=0))
    active_time_score = len(active_minutes)
    active_time_bucket = _active_time_bucket(active_time_score)
    active_time_humanized = _format_active_time_humanized(active_time_score)

    prep_signals = {
        "interview_info_opened": any(ev.event_type == "interview_info_opened" for ev in events),
        "interview_instruction_opened": any(ev.event_type == "interview_instruction_opened" for ev in events),
        "interview_link_copied": any(ev.event_type == "interview_link_copied" for ev in events),
        "interview_link_opened": any(ev.event_type == "interview_link_opened" for ev in events),
        "interview_preferences_submitted": bool(app and app.interview_preferences_submitted_at),
    }
    prep_count = sum(1 for v in prep_signals.values() if v)
    current_stage = app.current_stage if app else None
    if prep_count >= 3:
        prep_bucket = "strong"
    elif prep_count >= 1:
        prep_bucket = "some"
    elif current_stage in INTERVIEW_STAGES:
        prep_bucket = "none"
    else:
        prep_bucket = "neutral"

    reminder_time: datetime | None = None
    if app and app.interview_sessions:
        with_reminder = [s for s in app.interview_sessions if s.reminder_sent_at or s.reminder_requested_at]
        if with_reminder:
            latest = max(with_reminder, key=lambda s: s.updated_at)
            reminder_time = latest.reminder_sent_at or latest.reminder_requested_at
    reminder_response_bucket = "none"
    if reminder_time:
        later_actions = [ts for ts in timestamps if ts > reminder_time]
        if later_actions and min(later_actions) - reminder_time <= timedelta(hours=24):
            reminder_response_bucket = "reacted_fast"
        elif later_actions:
            reminder_response_bucket = "reacted_late"
        elif now - reminder_time > timedelta(hours=24):
            reminder_response_bucket = "ignored"
        else:
            reminder_response_bucket = "awaiting"

    stage_entered_at = _current_stage_entered_at(app) if app else None
    stage_stagnation_bucket = "none"
    if current_stage in CANDIDATE_ACTION_STAGES and last_activity_at is not None:
        inactive = now - last_activity_at
        if current_stage == ApplicationStage.application.value:
            if inactive >= timedelta(days=5):
                stage_stagnation_bucket = "severe"
            elif inactive >= timedelta(days=2):
                stage_stagnation_bucket = "mild"
        elif current_stage == ApplicationStage.interview.value:
            if inactive >= timedelta(days=3):
                stage_stagnation_bucket = "severe"
            elif inactive >= timedelta(days=1):
                stage_stagnation_bucket = "mild"

    stage_start_response_bucket = "neutral"
    if current_stage in CANDIDATE_ACTION_STAGES and stage_entered_at is not None:
        actions_after_stage = [ts for ts in timestamps if ts > stage_entered_at]
        if actions_after_stage and min(actions_after_stage) - stage_entered_at <= timedelta(hours=24):
            stage_start_response_bucket = "quick_start"
        elif not actions_after_stage and now - stage_entered_at > timedelta(hours=24):
            stage_start_response_bucket = "no_start"

    engagement_score = 0
    risk_score = 0
    contributions: dict[str, Any] = {
        "time_to_submit_bucket": time_to_submit_bucket,
        "last_online_bucket": last_online_bucket,
        "active_time_score": active_time_score,
        "active_time_bucket": active_time_bucket,
        "interview_preparation_score": prep_count,
        "interview_preparation_bucket": prep_bucket,
        "reminder_response_bucket": reminder_response_bucket,
        "stage_stagnation_bucket": stage_stagnation_bucket,
        "stage_start_response_bucket": stage_start_response_bucket,
    }

    if time_to_submit_bucket == "good":
        engagement_score += 2
    elif time_to_submit_bucket == "poor":
        engagement_score -= 2
        risk_score += 2

    if last_online_bucket == "good":
        engagement_score += 3
    elif last_online_bucket == "medium":
        risk_score += 2
    else:
        engagement_score -= 3
        risk_score += 4

    if active_time_bucket == "good":
        engagement_score += 2
    elif active_time_bucket == "medium":
        engagement_score += 1
        risk_score += 1
    else:
        engagement_score -= 2
        risk_score += 2

    if prep_bucket == "strong":
        engagement_score += 2
    elif prep_bucket == "some":
        engagement_score += 1
    elif prep_bucket == "none":
        engagement_score -= 1
        risk_score += 2

    if reminder_response_bucket == "reacted_fast":
        engagement_score += 1
    elif reminder_response_bucket == "reacted_late":
        risk_score += 1
    elif reminder_response_bucket == "ignored":
        engagement_score -= 2
        risk_score += 2

    if stage_stagnation_bucket == "mild":
        engagement_score -= 1
        risk_score += 2
    elif stage_stagnation_bucket == "severe":
        engagement_score -= 3
        risk_score += 4

    if stage_start_response_bucket == "quick_start":
        engagement_score += 1
    elif stage_start_response_bucket == "no_start":
        engagement_score -= 1
        risk_score += 1

    engagement_level = "High" if engagement_score >= 5 else "Medium" if engagement_score >= 1 else "Low"
    risk_level = "High" if risk_score >= 8 else "Medium" if risk_score >= 4 else "Low"

    contributions["engagement_score"] = engagement_score
    contributions["risk_score"] = risk_score

    if registered_at and timestamps:
        first_action_at = min(timestamps)
        start_fill = "начал сразу" if (first_action_at - registered_at) <= timedelta(hours=24) else "начал с задержкой"
    elif timestamps:
        start_fill = "начал"
    else:
        start_fill = "нет данных"

    has_draft = any(ev.event_type == "section_saved" for ev in events) or any(
        isinstance(ss, ApplicationSectionState) and ss.last_saved_at is not None for ss in (app.section_states if app else [])
    )
    docs_done = any(
        (candidate_user_id is None or d.uploaded_by_user_id == candidate_user_id) for d in docs
    )
    education_payload = _section_payload(app, "education")
    video_done = bool(str(education_payload.get("presentation_video_url") or "").strip())
    test_done = any(t.submitted_at is not None for t in test_answers) or any(
        ev.event_type == "internal_test_submitted" for ev in events
    )
    submitted_done = bool(app and app.submitted_at)
    interview_stage_entered_at = _first_interview_stage_entered_at(app)
    if app and app.interview_preferences_submitted_at:
        if interview_stage_entered_at and (app.interview_preferences_submitted_at - interview_stage_entered_at) > timedelta(hours=24):
            slot_signal = "выбран с задержкой"
        else:
            slot_signal = "выбран быстро"
    else:
        slot_signal = "не выбран"

    next_stage_reaction = (
        "вовремя"
        if stage_start_response_bucket == "quick_start"
        else "без старта"
        if stage_start_response_bucket == "no_start"
        else "с задержкой"
        if stage_stagnation_bucket in {"mild", "severe"}
        else "нет данных"
    )

    reminder_reaction = (
        "быстро"
        if reminder_response_bucket == "reacted_fast"
        else "поздно"
        if reminder_response_bucket == "reacted_late"
        else "игнор"
        if reminder_response_bucket == "ignored"
        else "нет данных"
    )

    signals = [
        f"Старт заполнения: {start_fill}.",
        f"Скорость прохождения анкеты: {speed_label}{' (есть задержка)' if speed_delay else ''}.",
        f"Суммарное активное время: {active_time_humanized}.",
        f"Черновик: {'сохранял' if has_draft else 'не сохранял'}.",
        f"Подача: {'завершена' if submitted_done else 'не завершена'}.",
        f"Реакция на следующий этап: {next_stage_reaction}.",
        f"Реакция на напоминания: {reminder_reaction}.",
        f"Выбор слота собеседования: {slot_signal}.",
    ]

    interpretation = _build_interpretation_lines(
        engagement_level=engagement_level,
        risk_level=risk_level,
        speed_label=speed_label,
        speed_delay=speed_delay,
        stage_start_response_bucket=stage_start_response_bucket,
        stage_stagnation_bucket=stage_stagnation_bucket,
        reminder_response_bucket=reminder_response_bucket,
    )
    final_line = _build_final_line(
        engagement_level=engagement_level,
        risk_level=risk_level,
        speed_label=speed_label,
        speed_delay=speed_delay,
        submitted_done=submitted_done,
    )

    return {
        "lastActivityAtIso": last_activity_at.isoformat() if last_activity_at else None,
        "lastActivityHumanized": last_activity_humanized,
        "activeTimeHumanized": active_time_humanized,
        "engagementLevel": engagement_level,
        "riskLevel": risk_level,
        "breakdown": contributions,
        "signals": signals,
        "interpretation": interpretation,
        "final": final_line,
    }


def _build_engagement_card(
    *,
    row: Any,
    app: Application | None,
    registered_at: datetime | None,
    candidate_user_id: UUID | None,
    events: list[CandidateActivityEvent],
    audits: list[AuditLog],
    docs: list[Document],
    test_answers: list[InternalTestAnswer],
    ai_answers: list[AIInterviewAnswer],
    now: datetime,
) -> dict[str, Any]:
    insight = _compute_engagement_insight(
        app=app,
        registered_at=registered_at,
        candidate_user_id=candidate_user_id,
        events=events,
        audits=audits,
        docs=docs,
        test_answers=test_answers,
        ai_answers=ai_answers,
        now=now,
    )

    return {
        "applicationId": str(row.application_id),
        "candidateFullName": row.candidate_full_name or "Кандидат",
        "program": row.program,
        "currentStage": row.current_stage,
        "lastActivityAtIso": insight.get("lastActivityAtIso"),
        "lastActivityHumanized": insight.get("lastActivityHumanized") or "нет активности",
        "activeTimeHumanized": insight.get("activeTimeHumanized"),
        "engagementLevel": insight.get("engagementLevel") or "Medium",
        "riskLevel": insight.get("riskLevel") or "Medium",
        "breakdown": insight.get("breakdown") or {},
    }


def build_engagement_insight_for_application(db: Session, *, application_id: UUID) -> dict[str, Any] | None:
    app = db.scalars(
        select(Application)
        .where(Application.id == application_id)
        .options(
            selectinload(Application.candidate_profile).selectinload(CandidateProfile.user),
            selectinload(Application.stage_history),
            selectinload(Application.section_states),
            selectinload(Application.interview_sessions),
        )
    ).first()
    if not app:
        return None

    profile = app.candidate_profile
    user = profile.user if profile else None
    candidate_user_id = user.id if user else None
    registered_at = user.created_at if user else app.created_at
    now = datetime.now(tz=UTC)

    events = db.scalars(
        select(CandidateActivityEvent).where(CandidateActivityEvent.application_id == application_id)
    ).all()
    audits = db.scalars(
        select(AuditLog).where(AuditLog.entity_type == "application", AuditLog.entity_id == application_id)
    ).all()
    docs = db.scalars(select(Document).where(Document.application_id == application_id)).all()
    test_answers = db.scalars(select(InternalTestAnswer).where(InternalTestAnswer.application_id == application_id)).all()
    ai_answers = db.scalars(select(AIInterviewAnswer).where(AIInterviewAnswer.application_id == application_id)).all()

    insight = _compute_engagement_insight(
        app=app,
        registered_at=registered_at,
        candidate_user_id=candidate_user_id,
        events=list(events),
        audits=list(audits),
        docs=list(docs),
        test_answers=list(test_answers),
        ai_answers=list(ai_answers),
        now=now,
    )
    return {
        "applicationId": str(app.id),
        "candidateFullName": (f"{profile.first_name} {profile.last_name}".strip() if profile else "Кандидат"),
        "currentStage": app.current_stage,
        "engagementLevel": insight.get("engagementLevel"),
        "riskLevel": insight.get("riskLevel"),
        "signals": insight.get("signals") or [],
        "interpretation": insight.get("interpretation") or [],
        "final": insight.get("final") or "",
        "breakdown": insight.get("breakdown") or {},
    }


def list_commission_engagement(
    db: Session,
    *,
    search: str | None,
    program: str | None,
    sort: str,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    rows = commission_repository.list_projections(
        db,
        stage=None,
        stage_status=None,
        attention_only=False,
        program=program,
        search=search,
        limit=10000,
        offset=0,
    )
    if not rows:
        apps = list(db.scalars(select(Application).order_by(Application.updated_at.desc()).limit(500)).all())
        for app in apps:
            if app.locked_after_submit or app.submitted_at is not None:
                commission_repository.upsert_projection_for_application(db, app)
        db.flush()
        rows = commission_repository.list_projections(
            db,
            stage=None,
            stage_status=None,
            attention_only=False,
            program=program,
            search=search,
            limit=10000,
            offset=0,
        )

    active_rows = [r for r in rows if application_to_commission_column(r.current_stage) in ACTIVE_COMMISSION_COLUMNS]
    if not active_rows:
        return {
            "filters": {"search": search or "", "program": program, "sort": sort},
            "totals": {"total": 0, "highRisk": 0, "mediumRisk": 0, "lowRisk": 0},
            "columns": [
                {"id": "high_risk", "title": "Высокий риск", "cards": []},
                {"id": "medium_risk", "title": "Средний риск", "cards": []},
                {"id": "low_risk", "title": "Низкий риск", "cards": []},
            ],
        }

    app_ids = [r.application_id for r in active_rows]
    apps = db.scalars(
        select(Application)
        .where(Application.id.in_(app_ids))
        .options(
            selectinload(Application.candidate_profile).selectinload(CandidateProfile.user),
            selectinload(Application.stage_history),
            selectinload(Application.section_states),
            selectinload(Application.interview_sessions),
        )
    ).unique().all()
    app_by_id = {a.id: a for a in apps}

    events_by_app: dict[UUID, list[CandidateActivityEvent]] = defaultdict(list)
    for row in db.scalars(
        select(CandidateActivityEvent).where(CandidateActivityEvent.application_id.in_(app_ids))
    ).all():
        events_by_app[row.application_id].append(row)

    audits_by_app: dict[UUID, list[AuditLog]] = defaultdict(list)
    for row in db.scalars(
        select(AuditLog).where(AuditLog.entity_type == "application", AuditLog.entity_id.in_(app_ids))
    ).all():
        audits_by_app[row.entity_id].append(row)

    docs_by_app: dict[UUID, list[Document]] = defaultdict(list)
    for row in db.scalars(select(Document).where(Document.application_id.in_(app_ids))).all():
        docs_by_app[row.application_id].append(row)

    tests_by_app: dict[UUID, list[InternalTestAnswer]] = defaultdict(list)
    for row in db.scalars(select(InternalTestAnswer).where(InternalTestAnswer.application_id.in_(app_ids))).all():
        tests_by_app[row.application_id].append(row)

    ai_answers_by_app: dict[UUID, list[AIInterviewAnswer]] = defaultdict(list)
    for row in db.scalars(select(AIInterviewAnswer).where(AIInterviewAnswer.application_id.in_(app_ids))).all():
        ai_answers_by_app[row.application_id].append(row)

    now = datetime.now(tz=UTC)
    cards: list[dict[str, Any]] = []
    for row in active_rows:
        app = app_by_id.get(row.application_id)
        profile = app.candidate_profile if app else None
        user = profile.user if profile else None
        candidate_user_id = user.id if user else None
        registered_at = user.created_at if user else (app.created_at if app else None)
        cards.append(
            _build_engagement_card(
                row=row,
                app=app,
                registered_at=registered_at,
                candidate_user_id=candidate_user_id,
                events=events_by_app.get(row.application_id, []),
                audits=audits_by_app.get(row.application_id, []),
                docs=docs_by_app.get(row.application_id, []),
                test_answers=tests_by_app.get(row.application_id, []),
                ai_answers=ai_answers_by_app.get(row.application_id, []),
                now=now,
            )
        )

    cards_sorted = sorted(
        cards,
        key=lambda x: (
            -RISK_RANK.get(str(x.get("riskLevel")), -1),
            x.get("lastActivityAtIso") is not None,
            x.get("lastActivityAtIso") or "",
            x.get("candidateFullName") or "",
        ),
    )
    page = cards_sorted[offset : offset + limit]

    high_cards = _sort_cards([c for c in page if c.get("riskLevel") == "High"], sort=sort)
    medium_cards = _sort_cards([c for c in page if c.get("riskLevel") == "Medium"], sort=sort)
    low_cards = _sort_cards([c for c in page if c.get("riskLevel") == "Low"], sort=sort)

    return {
        "filters": {"search": search or "", "program": program, "sort": sort},
        "totals": {
            "total": len(cards),
            "highRisk": sum(1 for c in cards if c.get("riskLevel") == "High"),
            "mediumRisk": sum(1 for c in cards if c.get("riskLevel") == "Medium"),
            "lowRisk": sum(1 for c in cards if c.get("riskLevel") == "Low"),
        },
        "columns": [
            {"id": "high_risk", "title": "Высокий риск", "cards": high_cards},
            {"id": "medium_risk", "title": "Средний риск", "cards": medium_cards},
            {"id": "low_risk", "title": "Низкий риск", "cards": low_cards},
        ],
    }
