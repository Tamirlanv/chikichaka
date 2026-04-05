"""Resolution-oriented summary after candidate completes AI interview (LLM + JSONB)."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from invision_api.commission.application.sidebar_service import _strip_technical_residue
from invision_api.models.ai_interview import AIInterviewQuestionSet
from invision_api.repositories import ai_interview_repository
from invision_api.services.ai_interview.context import build_interview_context
from invision_api.services.ai_provider import OpenAIProvider
from invision_api.services import audit_log_service
from invision_api.core.config import get_settings

logger = logging.getLogger(__name__)


def _persistable_error_message(exc: BaseException) -> str:
    """Human-readable, non-sensitive message for DB (may surface in commission UI)."""
    msg = str(exc).strip()
    if isinstance(exc, RuntimeError) and "OPENAI_API_KEY" in msg:
        return "Генерация сводки недоступна: не настроен сервис анализа."
    if "timeout" in msg.lower() or "timed out" in msg.lower():
        return "Превышено время ожидания при генерации сводки. Попробуйте позже."
    return "Не удалось сгенерировать сводку по AI-собеседованию. Попробуйте позже или обратитесь к администратору."


def _display_question_text(q: dict[str, Any]) -> str:
    return (q.get("commissionEditedText") or q.get("questionText") or "").strip()

RESOLUTION_SUMMARY_PROMPT_VERSION = "resolution_summary_v1"

_MAX_LIST_ITEMS = 24
_MAX_STRING_LEN = 2000


class ResolutionSummaryLLMOut(BaseModel):
    """Structured output from the model (before we add generatedAt / promptVersion)."""

    shortSummary: str = Field(..., min_length=1, max_length=_MAX_STRING_LEN)
    resolvedPoints: list[str] = Field(default_factory=list)
    unresolvedPoints: list[str] = Field(default_factory=list)
    newInformation: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"]

    @field_validator("resolvedPoints", "unresolvedPoints", "newInformation", mode="before")
    @classmethod
    def _cap_lists(cls, v: Any) -> list[str]:
        if not isinstance(v, list):
            return []
        out: list[str] = []
        for x in v[:_MAX_LIST_ITEMS]:
            s = _sanitize_line(str(x))
            if s:
                out.append(s)
        return out

    @field_validator("shortSummary", mode="before")
    @classmethod
    def _clean_summary(cls, v: Any) -> str:
        s = _sanitize_line(str(v) if v is not None else "")
        return s[:_MAX_STRING_LEN]


def _sanitize_line(s: str) -> str:
    t = _strip_technical_residue(s.strip())
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _compact_context_for_summary(ctx: dict[str, Any]) -> dict[str, Any]:
    """Drop oversized / redundant keys; context builder already truncates sections."""
    raw = json.dumps(ctx, ensure_ascii=False)
    if len(raw) <= 60000:
        return ctx
    return {
        "section_keys": ctx.get("section_keys"),
        "signals": ctx.get("signals"),
        "review_snapshot": ctx.get("review_snapshot"),
        "data_check": ctx.get("data_check"),
        "ai_review": ctx.get("ai_review"),
        "_truncated": True,
    }


def _build_user_payload(
    db: Session,
    application_id: UUID,
    row: AIInterviewQuestionSet,
) -> dict[str, Any]:
    ctx = build_interview_context(db, application_id)
    ctx_compact = _compact_context_for_summary(ctx)

    answer_map = {r.question_id: r.answer_text for r in ai_interview_repository.list_answers(db, application_id)}
    qa: list[dict[str, Any]] = []
    for q in sorted(row.questions or [], key=lambda x: x.get("sortOrder", 0)):
        qtext = _display_question_text(q)
        if not qtext:
            continue
        qid = str(q.get("id") or "")
        rd = (q.get("reasonDescription") or q.get("reason_description") or "").strip()
        ce = (q.get("commissionEditedText") or "").strip()
        qa.append(
            {
                "questionText": qtext,
                "reasonDescription": rd or None,
                "commissionEditedText": ce or None,
                "answerText": str(answer_map.get(qid, "") or "").strip(),
            }
        )

    return {
        "interviewContext": ctx_compact,
        "questionsAndAnswers": qa,
    }


def generate_resolution_summary_llm(
    user_payload: dict[str, Any], *, application_id: str | None = None
) -> dict[str, Any]:
    """Call OpenAI JSON mode; validate; return storable dict including generatedAt."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    provider = OpenAIProvider()
    system = (
        "You write a compact resolution-oriented summary for university admissions committee reviewers (Russian). "
        "Compare the applicant's AI interview answers with the prior application context and signals. "
        "Do not repeat every question; focus on what was clarified vs what remains open. "
        "No admissions decision. No protected-attribute inference. "
        "Do not echo internal field names, JSON keys, pipeline labels, or debugging tokens. "
        f"Return a single JSON object with keys: shortSummary (string, 2–4 sentences), "
        f"resolvedPoints (array of short strings, max {_MAX_LIST_ITEMS} items), "
        f"unresolvedPoints (array, max {_MAX_LIST_ITEMS}), newInformation (array, max {_MAX_LIST_ITEMS}), "
        "confidence (one of: low, medium, high)."
    )
    user_message = json.dumps(user_payload, ensure_ascii=False)[:80000]
    t0 = time.perf_counter()
    raw = provider.committee_structured_summary(
        prompt_version=RESOLUTION_SUMMARY_PROMPT_VERSION,
        compact_payload={},
        system_prompt=system,
        user_message=user_message,
        snapshot_flow="ai_interview_resolution_summary",
        snapshot_application_id=application_id or "",
    )
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    logger.info("resolution_summary: LLM ok in %sms", elapsed_ms)

    if not isinstance(raw, dict):
        raise ValueError("LLM returned non-object JSON")

    parsed = ResolutionSummaryLLMOut.model_validate(raw)
    now = datetime.now(tz=UTC)
    out: dict[str, Any] = {
        "shortSummary": parsed.shortSummary,
        "resolvedPoints": parsed.resolvedPoints,
        "unresolvedPoints": parsed.unresolvedPoints,
        "newInformation": parsed.newInformation,
        "confidence": parsed.confidence,
        "generatedAt": now.isoformat(),
        "promptVersion": RESOLUTION_SUMMARY_PROMPT_VERSION,
    }
    return out


def try_generate_and_persist_resolution_summary(
    db: Session,
    application_id: UUID,
    row: AIInterviewQuestionSet,
) -> None:
    """Best-effort generation; on failure sets resolution_summary_error and does not raise."""
    if row.resolution_summary is not None:
        logger.info(
            "resolution_summary: skip generation (already present) application_id=%s session_id=%s",
            application_id,
            row.id,
        )
        return

    try:
        payload = _build_user_payload(db, application_id, row)
        summary = generate_resolution_summary_llm(payload, application_id=str(application_id))
        row.resolution_summary = summary
        row.resolution_summary_error = None
        db.flush()
        logger.info(
            "resolution_summary: persisted application_id=%s session_id=%s generated_at=%s",
            application_id,
            row.id,
            summary.get("generatedAt"),
        )
        audit_log_service.write_audit(
            db,
            entity_type="application",
            entity_id=application_id,
            action="ai_interview_resolution_summary_generated",
            actor_user_id=None,
            after_data={
                "session_id": str(row.id),
                "generated_at": summary.get("generatedAt"),
                "prompt_version": summary.get("promptVersion"),
            },
        )
    except Exception as e:
        safe = _persistable_error_message(e)
        logger.warning(
            "resolution_summary: generation failed application_id=%s session_id=%s safe_message=%s",
            application_id,
            row.id,
            safe,
            exc_info=True,
        )
        row.resolution_summary_error = safe[:2000]
        db.flush()
