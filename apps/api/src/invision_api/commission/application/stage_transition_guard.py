"""Central resolver for commission Kanban stage advances (single source of truth for guards)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from invision_api.commission.application import kanban_border_hints
from invision_api.models.application import AIReviewMetadata, Application, InterviewSession
from invision_api.models.enums import ApplicationStage, DataCheckRunStatus
from invision_api.repositories import ai_interview_repository
from invision_api.services.ai_interview.data_readiness import get_data_check_overall_status
from invision_api.services.stage_transition_policy import TransitionName

_COMMISSION_INTERVIEW_SESSION_INDEX = 0


def _get_commission_interview_session(db: Session, application_id: UUID) -> InterviewSession | None:
    """Same as interview_preference_window.get_commission_interview_session (avoid import cycle)."""
    return db.scalars(
        select(InterviewSession)
        .where(
            InterviewSession.application_id == application_id,
            InterviewSession.session_index == _COMMISSION_INTERVIEW_SESSION_INDEX,
        )
        .order_by(InterviewSession.created_at.desc())
        .limit(1)
    ).first()


class StageAdvanceBlockCode(StrEnum):
    MANUAL_FROM_DATA_CHECK_FORBIDDEN = "MANUAL_FROM_DATA_CHECK_FORBIDDEN"
    STAGE_ONE_NOT_READY = "STAGE_ONE_NOT_READY"
    RUBRIC_INCOMPLETE = "RUBRIC_INCOMPLETE"
    AI_QUESTIONS_NOT_APPROVED = "AI_QUESTIONS_NOT_APPROVED"
    AI_INTERVIEW_INCOMPLETE = "AI_INTERVIEW_INCOMPLETE"
    COMMISSION_INTERVIEW_NOT_SCHEDULED = "COMMISSION_INTERVIEW_NOT_SCHEDULED"
    COMMISSION_INTERVIEW_DATE_NOT_REACHED = "COMMISSION_INTERVIEW_DATE_NOT_REACHED"
    COMMISSION_INTERVIEW_OUTCOME_MISSING = "COMMISSION_INTERVIEW_OUTCOME_MISSING"
    NO_NEXT_STAGE = "NO_NEXT_STAGE"


# Query param values for /commission/applications/[id] (see web page mapping)
INTERVIEW_SUB_TAB_PREP = "prep"
INTERVIEW_SUB_TAB_AI = "ai"
INTERVIEW_SUB_TAB_COMMISSION = "commission"


def _candidate_full_name(app: Application) -> str:
    cp = app.candidate_profile
    if cp is None:
        return "Кандидат"
    return f"{cp.first_name} {cp.last_name}".strip() or "Кандидат"


def _has_ai_summary(db: Session, application_id: UUID) -> bool:
    row = db.scalars(
        select(AIReviewMetadata.summary_text)
        .where(AIReviewMetadata.application_id == application_id)
        .order_by(AIReviewMetadata.created_at.desc())
        .limit(1)
    ).first()
    return bool(row and row[0])


def _primary_open(application_id: UUID, *, interview_sub_tab: str | None = None) -> dict[str, Any]:
    q: dict[str, str] = {}
    if interview_sub_tab:
        q["interviewSubTab"] = interview_sub_tab
    return {
        "kind": "open_application",
        "applicationId": str(application_id),
        "query": q,
    }


@dataclass(frozen=True)
class StageAdvanceResolution:
    allowed: bool
    transition: TransitionName | None
    candidate_full_name: str
    target_stage_label_ru: str
    block_code: StageAdvanceBlockCode | None
    message: str
    primary_action: dict[str, Any] | None


def _target_label_for_transition(transition: TransitionName) -> str:
    if transition == TransitionName.screening_passed:
        return "Оценка заявки"
    if transition == TransitionName.review_complete:
        return "Собеседование"
    if transition == TransitionName.interview_complete:
        return "Решение комиссии"
    if transition == TransitionName.human_advances_to_decision:
        return "Решение комиссии"
    return "следующий этап"


def resolve_kanban_advance(db: Session, application_id: UUID) -> StageAdvanceResolution:
    """
    Decide whether POST /stage/advance may proceed and which transition applies.
    Does not mutate the database.
    """
    app = db.scalars(
        select(Application)
        .where(Application.id == application_id)
        .options(selectinload(Application.candidate_profile))
    ).first()
    if not app:
        return StageAdvanceResolution(
            allowed=False,
            transition=None,
            candidate_full_name="",
            target_stage_label_ru="",
            block_code=StageAdvanceBlockCode.NO_NEXT_STAGE,
            message="Заявка не найдена.",
            primary_action=None,
        )

    name = _candidate_full_name(app)
    stage = app.current_stage

    if stage == ApplicationStage.initial_screening.value:
        overall = get_data_check_overall_status(db, application_id)
        if overall in {DataCheckRunStatus.partial.value, DataCheckRunStatus.failed.value}:
            return StageAdvanceResolution(
                allowed=True,
                transition=TransitionName.screening_passed,
                candidate_full_name=name,
                target_stage_label_ru=_target_label_for_transition(TransitionName.screening_passed),
                block_code=None,
                message="",
                primary_action=None,
            )
        if overall in {DataCheckRunStatus.pending.value, DataCheckRunStatus.running.value} or overall is None:
            message = (
                "Обработка данных ещё идёт. Дождитесь завершения проверки, "
                "после чего будет доступен ручной перенос при наличии проблем."
            )
        elif overall == DataCheckRunStatus.ready.value:
            message = (
                "Проверка данных завершилась успешно. "
                "Переход на следующий этап выполняется автоматически."
            )
        else:
            message = "Ручной перенос с этапа «Проверка данных» сейчас недоступен."
        return StageAdvanceResolution(
            allowed=False,
            transition=None,
            candidate_full_name=name,
            target_stage_label_ru="Оценка заявки",
            block_code=StageAdvanceBlockCode.MANUAL_FROM_DATA_CHECK_FORBIDDEN,
            message=message,
            primary_action=_primary_open(application_id),
        )

    if stage == ApplicationStage.application_review.value:
        has_ai = _has_ai_summary(db, application_id)
        if not kanban_border_hints.stage_one_data_ready(db, application_id, has_ai_summary=has_ai):
            return StageAdvanceResolution(
                allowed=False,
                transition=None,
                candidate_full_name=name,
                target_stage_label_ru="Собеседование",
                block_code=StageAdvanceBlockCode.STAGE_ONE_NOT_READY,
                message="Заявка ещё не готова к переходу: требуется готовность данных и AI-сводки первого этапа.",
                primary_action=_primary_open(application_id),
            )
        if not kanban_border_hints.rubric_three_sections_complete(db, application_id):
            return StageAdvanceResolution(
                allowed=False,
                transition=None,
                candidate_full_name=name,
                target_stage_label_ru="Собеседование",
                block_code=StageAdvanceBlockCode.RUBRIC_INCOMPLETE,
                message="Заявка еще не готова к переходу. Комиссия не заполнила все обязательные оценки.",
                primary_action=_primary_open(application_id),
            )
        try:
            from invision_api.services.ai_interview.service import (
                assert_approved_ai_interview_for_internal_transition,
            )

            assert_approved_ai_interview_for_internal_transition(db, application_id)
        except ValueError:
            return StageAdvanceResolution(
                allowed=False,
                transition=None,
                candidate_full_name=name,
                target_stage_label_ru="Собеседование",
                block_code=StageAdvanceBlockCode.AI_QUESTIONS_NOT_APPROVED,
                message=(
                    "Предупреждение: перед переходом на этап собеседования необходимо одобрить вопросы "
                    "для AI-собеседования."
                ),
                primary_action=_primary_open(application_id, interview_sub_tab=INTERVIEW_SUB_TAB_PREP),
            )
        return StageAdvanceResolution(
            allowed=True,
            transition=TransitionName.review_complete,
            candidate_full_name=name,
            target_stage_label_ru=_target_label_for_transition(TransitionName.review_complete),
            block_code=None,
            message="",
            primary_action=None,
        )

    if stage == ApplicationStage.interview.value:
        qs = ai_interview_repository.get_question_set_for_application(db, application_id)
        if not qs or qs.candidate_completed_at is None:
            return StageAdvanceResolution(
                allowed=False,
                transition=None,
                candidate_full_name=name,
                target_stage_label_ru="Решение комиссии",
                block_code=StageAdvanceBlockCode.AI_INTERVIEW_INCOMPLETE,
                message="Предупреждение: кандидат еще не завершил AI-собеседование.",
                primary_action=_primary_open(application_id, interview_sub_tab=INTERVIEW_SUB_TAB_AI),
            )

        sess = _get_commission_interview_session(db, application_id)
        if sess is None or sess.scheduled_at is None:
            return StageAdvanceResolution(
                allowed=False,
                transition=None,
                candidate_full_name=name,
                target_stage_label_ru="Решение комиссии",
                block_code=StageAdvanceBlockCode.COMMISSION_INTERVIEW_NOT_SCHEDULED,
                message="Предупреждение: собеседование с комиссией еще не назначено.",
                primary_action=_primary_open(application_id, interview_sub_tab=INTERVIEW_SUB_TAB_COMMISSION),
            )

        now = datetime.now(tz=UTC)
        if sess.scheduled_at > now:
            return StageAdvanceResolution(
                allowed=False,
                transition=None,
                candidate_full_name=name,
                target_stage_label_ru="Решение комиссии",
                block_code=StageAdvanceBlockCode.COMMISSION_INTERVIEW_DATE_NOT_REACHED,
                message="Предупреждение: дата собеседования с комиссией еще не наступила.",
                primary_action=_primary_open(application_id, interview_sub_tab=INTERVIEW_SUB_TAB_COMMISSION),
            )

        if sess.outcome_recorded_at is None:
            return StageAdvanceResolution(
                allowed=False,
                transition=None,
                candidate_full_name=name,
                target_stage_label_ru="Решение комиссии",
                block_code=StageAdvanceBlockCode.COMMISSION_INTERVIEW_OUTCOME_MISSING,
                message="Предупреждение: требуется подтверждение комиссии по итогам проведенного собеседования.",
                primary_action=_primary_open(application_id, interview_sub_tab=INTERVIEW_SUB_TAB_COMMISSION),
            )

        return StageAdvanceResolution(
            allowed=True,
            transition=TransitionName.interview_complete,
            candidate_full_name=name,
            target_stage_label_ru=_target_label_for_transition(TransitionName.interview_complete),
            block_code=None,
            message="",
            primary_action=None,
        )

    if stage == ApplicationStage.committee_review.value:
        return StageAdvanceResolution(
            allowed=True,
            transition=TransitionName.human_advances_to_decision,
            candidate_full_name=name,
            target_stage_label_ru=_target_label_for_transition(TransitionName.human_advances_to_decision),
            block_code=None,
            message="",
            primary_action=None,
        )

    return StageAdvanceResolution(
        allowed=False,
        transition=None,
        candidate_full_name=name,
        target_stage_label_ru="",
        block_code=StageAdvanceBlockCode.NO_NEXT_STAGE,
        message="Нет допустимого следующего этапа для этой заявки.",
        primary_action=_primary_open(application_id),
    )


def resolution_to_preview_dict(r: StageAdvanceResolution) -> dict[str, Any]:
    """JSON-serializable body for GET stage-advance-preview."""
    base: dict[str, Any] = {
        "allowed": r.allowed,
        "candidateFullName": r.candidate_full_name,
        "targetStageLabel": r.target_stage_label_ru,
    }
    if r.allowed:
        base["confirm"] = {
            "title": "Подтверждение",
            "message": (
                f"Вы уверены, что хотите переместить {r.candidate_full_name} на этап {r.target_stage_label_ru}?"
            ),
            "confirmLabel": "Подтвердить",
            "cancelLabel": "Отмена",
        }
        base["transition"] = r.transition.value if r.transition else None
    else:
        has_subtab = bool((r.primary_action or {}).get("query", {}).get("interviewSubTab"))
        base["blocked"] = {
            "code": r.block_code.value if r.block_code else None,
            "message": r.message,
            "confirmLabel": "Перейти" if has_subtab else "Проверить",
            "cancelLabel": "Отмена",
            "primaryAction": r.primary_action,
        }
    return base


def http_detail_from_resolution(r: StageAdvanceResolution) -> dict[str, Any]:
    """FastAPI HTTPException detail payload for 409."""
    prev = resolution_to_preview_dict(r)
    prev["allowed"] = False
    return {
        "code": r.block_code.value if r.block_code else StageAdvanceBlockCode.NO_NEXT_STAGE.value,
        "message": r.message,
        "primaryAction": r.primary_action,
        "preview": prev,
    }
