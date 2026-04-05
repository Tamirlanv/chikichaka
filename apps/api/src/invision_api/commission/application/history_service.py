from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session

from invision_api.models.application import AuditLog
from invision_api.models.candidate_validation_orchestration import CandidateValidationRun
from invision_api.models.commission import ApplicationCommissionProjection
from invision_api.models.user import User

_VALID_EVENT_FILTERS = {
    "all",
    "commission",
    "system",
    "candidates",
    "stage",
    "interview",
    "decision",
}
_VALID_SORTS = {"newest", "oldest"}

_STAGE_RU: dict[str, str] = {
    "application": "Заполнение анкеты",
    "initial_screening": "Проверка данных",
    "data_check": "Проверка данных",
    "application_review": "Оценка заявки",
    "interview": "Собеседование",
    "committee_review": "Решение комиссии",
    "committee_decision": "Решение комиссии",
    "decision": "Результат",
    "result": "Результат",
}

_FINAL_DECISION_RU: dict[str, str] = {
    "move_forward": "Перевести дальше",
    "invite_interview": "Приглашение на собеседование",
    "waitlist": "Лист ожидания",
    "enrolled": "Зачислен",
    "reject": "Отказ",
}

_SECTION_LABELS_RU: dict[str, str] = {
    "personal": "Личная информация",
    "test": "Тест",
    "motivation": "Мотивация",
    "path": "Путь",
    "achievements": "Достижения",
}

# Only meaningful high-level actions for the commission timeline.
_AUDIT_EVENT_TAGS: dict[str, tuple[str, ...]] = {
    "application_submitted": ("candidate", "stage"),
    "application_reopened_for_resubmit": ("candidate", "stage"),
    "stage_advanced": ("commission", "stage"),
    "stage_status_changed": ("commission", "stage"),
    "attention_flag_changed": ("commission",),
    "comment_added": ("commission",),
    "rubric_updated": ("commission",),
    "section_scores_updated": ("commission",),
    "internal_recommendation_updated": ("commission", "decision"),
    "final_decision_set": ("commission", "decision"),
    "application_archived_by_commission": ("commission", "decision"),
    "ai_interview_generated": ("commission", "interview"),
    "ai_interview_draft_updated": ("commission", "interview"),
    "ai_interview_approved": ("commission", "interview"),
    "candidate_ai_interview_completed": ("candidate", "interview"),
    "candidate_interview_preferences_submitted": ("candidate", "interview"),
    "commission_interview_scheduled": ("commission", "interview"),
    "commission_interview_outcome_recorded": ("commission", "interview"),
    "interview_preference_window_expired": ("system", "interview"),
}


@dataclass(frozen=True)
class _AppCtx:
    application_id: UUID
    candidate_full_name: str
    program: str | None
    current_stage: str | None


def _normalize_event_filter(value: str | None) -> str:
    raw = (value or "all").strip().lower()
    if raw not in _VALID_EVENT_FILTERS:
        raise ValueError("Некорректный eventType")
    return raw


def _normalize_sort(value: str | None) -> str:
    raw = (value or "newest").strip().lower()
    if raw not in _VALID_SORTS:
        raise ValueError("Некорректный sort")
    return raw


def _stage_label(value: Any) -> str:
    key = str(value or "").strip().lower()
    return _STAGE_RU.get(key, "этап")


def _decision_label(value: Any) -> str:
    key = str(value or "").strip().lower()
    return _FINAL_DECISION_RU.get(key, key or "решение")


def _status_label(value: Any) -> str:
    key = str(value or "").strip().lower()
    labels = {
        "new": "новый",
        "in_review": "на рассмотрении",
        "needs_attention": "требует внимания",
        "approved": "подтвержден",
        "rejected": "отклонен",
    }
    return labels.get(key, key or "статус обновлен")


def _section_label(value: Any) -> str:
    key = str(value or "").strip().lower()
    return _SECTION_LABELS_RU.get(key, key or "раздел")


def _initiator(action: str, actor_name: str | None) -> tuple[str, str]:
    if action.startswith("candidate_") or action in {
        "application_submitted",
        "application_reopened_for_resubmit",
        "candidate_ai_interview_completed",
    }:
        return (actor_name or "Кандидат", "candidate")
    if actor_name:
        return (actor_name, "commission")
    return ("Система", "system")


def _history_type_label(tags: tuple[str, ...]) -> str:
    if "decision" in tags:
        return "Решение"
    if "interview" in tags:
        return "Собеседование"
    if "stage" in tags:
        return "Перемещение по этапам"
    if "candidate" in tags:
        return "Кандидат"
    if "system" in tags:
        return "Система"
    return "Комиссия"


def _render_description(audit: AuditLog, ctx: _AppCtx) -> str:
    action = audit.action
    after = audit.after_data if isinstance(audit.after_data, dict) else {}
    if action == "application_submitted":
        return f"Кандидат {ctx.candidate_full_name} отправил анкету."
    if action == "application_reopened_for_resubmit":
        return f"Кандидат {ctx.candidate_full_name} вернул анкету на доработку."
    if action == "stage_advanced":
        target_stage = _stage_label(after.get("current_stage"))
        return f"Кандидат {ctx.candidate_full_name} переведен на этап «{target_stage}»."
    if action == "stage_status_changed":
        stage = _stage_label(after.get("stage") or ctx.current_stage)
        status = _status_label(after.get("status"))
        return f"Обновлен статус этапа «{stage}»: {status}."
    if action == "attention_flag_changed":
        return f"Для кандидата {ctx.candidate_full_name} изменен флаг внимания комиссии."
    if action == "comment_added":
        return f"Добавлен комментарий по кандидату {ctx.candidate_full_name}."
    if action == "rubric_updated":
        return f"Обновлены rubric-оценки по кандидату {ctx.candidate_full_name}."
    if action == "section_scores_updated":
        section = _section_label(after.get("section"))
        return f"Обновлены оценки комиссии по разделу «{section}»."
    if action == "internal_recommendation_updated":
        return f"Обновлена внутренняя рекомендация по кандидату {ctx.candidate_full_name}."
    if action == "final_decision_set":
        return f"Принято итоговое решение: {_decision_label(after.get('final_decision'))}."
    if action == "application_archived_by_commission":
        return f"Заявка кандидата {ctx.candidate_full_name} перенесена в архив."
    if action == "ai_interview_generated":
        return f"Сформирован черновик вопросов AI-собеседования для кандидата {ctx.candidate_full_name}."
    if action == "ai_interview_draft_updated":
        return f"Комиссия обновила черновик вопросов AI-собеседования."
    if action == "ai_interview_approved":
        return f"Комиссия одобрила вопросы AI-собеседования для кандидата {ctx.candidate_full_name}."
    if action == "candidate_ai_interview_completed":
        return f"Кандидат {ctx.candidate_full_name} завершил AI-собеседование."
    if action == "candidate_interview_preferences_submitted":
        return f"Кандидат {ctx.candidate_full_name} выбрал предпочтительное время собеседования."
    if action == "commission_interview_scheduled":
        return f"Назначено собеседование кандидату {ctx.candidate_full_name}."
    if action == "commission_interview_outcome_recorded":
        return f"Зафиксирован итог собеседования по кандидату {ctx.candidate_full_name}."
    if action == "interview_preference_window_expired":
        return (
            f"Система закрыла окно выбора времени для кандидата {ctx.candidate_full_name}: срок ожидания истек."
        )
    return "Событие по заявке обновлено."


def _event_matches_filter(tags: tuple[str, ...], event_filter: str) -> bool:
    if event_filter == "all":
        return True
    if event_filter == "candidates":
        return "candidate" in tags
    if event_filter == "commission":
        return "commission" in tags
    if event_filter == "system":
        return "system" in tags
    if event_filter == "stage":
        return "stage" in tags
    if event_filter == "interview":
        return "interview" in tags
    if event_filter == "decision":
        return "decision" in tags
    return False


def _load_app_contexts(db: Session, *, search: str | None, program: str | None) -> dict[UUID, _AppCtx]:
    stmt = select(
        ApplicationCommissionProjection.application_id,
        ApplicationCommissionProjection.candidate_full_name,
        ApplicationCommissionProjection.program,
        ApplicationCommissionProjection.current_stage,
    )
    if program:
        stmt = stmt.where(ApplicationCommissionProjection.program == program)
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                ApplicationCommissionProjection.candidate_full_name.ilike(q),
                ApplicationCommissionProjection.program.ilike(q),
                cast(ApplicationCommissionProjection.application_id, String).ilike(q),
            )
        )

    rows = db.execute(stmt).all()
    out: dict[UUID, _AppCtx] = {}
    for app_id, full_name, row_program, current_stage in rows:
        out[app_id] = _AppCtx(
            application_id=app_id,
            candidate_full_name=(str(full_name or "").strip() or "Кандидат"),
            program=row_program,
            current_stage=current_stage,
        )
    return out


def _load_single_app_context(db: Session, application_id: UUID) -> _AppCtx | None:
    row = db.execute(
        select(
            ApplicationCommissionProjection.application_id,
            ApplicationCommissionProjection.candidate_full_name,
            ApplicationCommissionProjection.program,
            ApplicationCommissionProjection.current_stage,
        ).where(ApplicationCommissionProjection.application_id == application_id)
    ).first()
    if row is None:
        return None
    app_id, full_name, row_program, current_stage = row
    return _AppCtx(
        application_id=app_id,
        candidate_full_name=(str(full_name or "").strip() or "Кандидат"),
        program=row_program,
        current_stage=current_stage,
    )


def _actor_names_by_id(db: Session, actor_ids: set[UUID]) -> dict[UUID, str]:
    if not actor_ids:
        return {}
    rows = db.execute(select(User.id, User.email).where(User.id.in_(actor_ids))).all()
    out: dict[UUID, str] = {}
    for uid, email in rows:
        out[uid] = str(email or uid)
    return out


def _normalize_audit_events(
    *,
    audit_rows: list[AuditLog],
    app_ctx: dict[UUID, _AppCtx],
    actor_names: dict[UUID, str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in audit_rows:
        tags = _AUDIT_EVENT_TAGS.get(row.action)
        if not tags:
            continue
        ctx = app_ctx.get(row.entity_id)
        if not ctx:
            continue
        actor_name = actor_names.get(row.actor_user_id) if row.actor_user_id else None
        initiator, initiator_type = _initiator(row.action, actor_name)
        out.append(
            {
                "id": f"audit:{row.id}",
                "applicationId": str(ctx.application_id),
                "candidateFullName": ctx.candidate_full_name,
                "program": ctx.program,
                "currentStage": ctx.current_stage,
                "eventType": _history_type_label(tags),
                "eventCategory": initiator_type,
                "description": _render_description(row, ctx),
                "initiator": initiator,
                "timestamp": row.created_at.isoformat(),
                "_tags": tags,
                "_ts": row.created_at,
            }
        )
    return out


def _normalize_data_check_events(
    *,
    runs: list[CandidateValidationRun],
    app_ctx: dict[UUID, _AppCtx],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for run in runs:
        ctx = app_ctx.get(run.application_id)
        if not ctx:
            continue
        started_at = run.created_at
        out.append(
            {
                "id": f"data-check:{run.id}:started",
                "applicationId": str(ctx.application_id),
                "candidateFullName": ctx.candidate_full_name,
                "program": ctx.program,
                "currentStage": ctx.current_stage,
                "eventType": "Перемещение по этапам",
                "eventCategory": "system",
                "description": f"Система запустила проверку данных кандидата {ctx.candidate_full_name}.",
                "initiator": "Система",
                "timestamp": started_at.isoformat(),
                "_tags": ("system", "stage"),
                "_ts": started_at,
            }
        )

        status = str(run.overall_status or "").strip().lower()
        terminal = {"ready", "partial", "failed"}
        finished_at = run.updated_at
        if status not in terminal:
            continue
        if finished_at is None:
            continue

        if status == "ready":
            line = f"Система завершила проверку данных кандидата {ctx.candidate_full_name} успешно."
        elif status == "partial":
            line = (
                f"Система завершила проверку данных кандидата {ctx.candidate_full_name} с частичными проблемами."
            )
        else:
            line = f"Система завершила проверку данных кандидата {ctx.candidate_full_name} с ошибками."

        out.append(
            {
                "id": f"data-check:{run.id}:finished",
                "applicationId": str(ctx.application_id),
                "candidateFullName": ctx.candidate_full_name,
                "program": ctx.program,
                "currentStage": ctx.current_stage,
                "eventType": "Перемещение по этапам",
                "eventCategory": "system",
                "description": line,
                "initiator": "Система",
                "timestamp": finished_at.isoformat(),
                "_tags": ("system", "stage"),
                "_ts": finished_at,
            }
        )
    return out


def _sorted_and_paginated(
    *,
    events: list[dict[str, Any]],
    event_filter: str,
    sort: str,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    filtered = [e for e in events if _event_matches_filter(e.get("_tags", ()), event_filter)]
    reverse = sort == "newest"
    filtered.sort(
        key=lambda e: (e.get("_ts") or datetime.min.replace(tzinfo=UTC)).timestamp(),
        reverse=reverse,
    )
    total = len(filtered)
    page = filtered[offset: offset + limit]
    for item in page:
        item.pop("_tags", None)
        item.pop("_ts", None)
    return page, total


def list_commission_history_events(
    db: Session,
    *,
    search: str | None,
    program: str | None,
    event_type: str,
    sort: str,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    event_filter = _normalize_event_filter(event_type)
    sort_mode = _normalize_sort(sort)

    app_ctx = _load_app_contexts(db, search=search, program=program)
    if not app_ctx:
        return {
            "items": [],
            "total": 0,
            "filters": {
                "search": search or "",
                "program": program,
                "eventType": event_filter,
                "sort": sort_mode,
            },
        }

    app_ids = list(app_ctx.keys())
    fetch_cap = max(500, min(5000, (offset + limit) * 8))

    order_expr = AuditLog.created_at.desc() if sort_mode == "newest" else AuditLog.created_at.asc()
    audit_rows = list(
        db.scalars(
            select(AuditLog)
            .where(
                AuditLog.entity_type == "application",
                AuditLog.entity_id.in_(app_ids),
                AuditLog.action.in_(tuple(_AUDIT_EVENT_TAGS.keys())),
            )
            .order_by(order_expr)
            .limit(fetch_cap)
        ).all()
    )

    actor_ids = {row.actor_user_id for row in audit_rows if row.actor_user_id is not None}
    actor_names = _actor_names_by_id(db, actor_ids)

    runs = list(
        db.scalars(
            select(CandidateValidationRun)
            .where(CandidateValidationRun.application_id.in_(app_ids))
            .order_by(
                CandidateValidationRun.created_at.desc()
                if sort_mode == "newest"
                else CandidateValidationRun.created_at.asc()
            )
            .limit(fetch_cap)
        ).all()
    )

    events = _normalize_audit_events(audit_rows=audit_rows, app_ctx=app_ctx, actor_names=actor_names)
    events.extend(_normalize_data_check_events(runs=runs, app_ctx=app_ctx))

    items, total = _sorted_and_paginated(
        events=events,
        event_filter=event_filter,
        sort=sort_mode,
        limit=limit,
        offset=offset,
    )
    return {
        "items": items,
        "total": total,
        "filters": {
            "search": search or "",
            "program": program,
            "eventType": event_filter,
            "sort": sort_mode,
        },
    }


def list_application_history_events(
    db: Session,
    *,
    application_id: UUID,
    event_type: str,
    sort: str,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    event_filter = _normalize_event_filter(event_type)
    sort_mode = _normalize_sort(sort)

    single_ctx = _load_single_app_context(db, application_id)
    if single_ctx is None:
        return {
            "applicationId": str(application_id),
            "items": [],
            "total": 0,
            "filters": {"eventType": event_filter, "sort": sort_mode},
        }

    ctx = {application_id: single_ctx}
    order_expr = AuditLog.created_at.desc() if sort_mode == "newest" else AuditLog.created_at.asc()
    audit_rows = list(
        db.scalars(
            select(AuditLog)
            .where(
                AuditLog.entity_type == "application",
                AuditLog.entity_id == application_id,
                AuditLog.action.in_(tuple(_AUDIT_EVENT_TAGS.keys())),
            )
            .order_by(order_expr)
            .limit(max(500, min(5000, (offset + limit) * 8)))
        ).all()
    )

    actor_ids = {row.actor_user_id for row in audit_rows if row.actor_user_id is not None}
    actor_names = _actor_names_by_id(db, actor_ids)

    runs = list(
        db.scalars(
            select(CandidateValidationRun)
            .where(CandidateValidationRun.application_id == application_id)
            .order_by(
                CandidateValidationRun.created_at.desc()
                if sort_mode == "newest"
                else CandidateValidationRun.created_at.asc()
            )
            .limit(max(500, min(5000, (offset + limit) * 8)))
        ).all()
    )

    events = _normalize_audit_events(audit_rows=audit_rows, app_ctx=ctx, actor_names=actor_names)
    events.extend(_normalize_data_check_events(runs=runs, app_ctx=ctx))

    items, total = _sorted_and_paginated(
        events=events,
        event_filter=event_filter,
        sort=sort_mode,
        limit=limit,
        offset=offset,
    )
    return {
        "applicationId": str(application_id),
        "items": items,
        "total": total,
        "filters": {"eventType": event_filter, "sort": sort_mode},
    }
