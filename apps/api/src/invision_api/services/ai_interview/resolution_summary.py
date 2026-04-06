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
    followUpFocus: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"]

    @field_validator("resolvedPoints", "unresolvedPoints", "newInformation", "followUpFocus", mode="before")
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
        "issue_candidates": ctx.get("issue_candidates"),
        "_truncated": True,
    }


def _short_text(value: str | None, *, max_len: int = 180) -> str:
    if not value:
        return ""
    text = _sanitize_line(value)
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip(" ,.;:") + "…"


def _first_sentence(value: str | None, *, max_len: int = 180) -> str:
    if not value:
        return ""
    text = _sanitize_line(value)
    for token in (".", "!", "?"):
        idx = text.find(token)
        if idx > 20:
            text = text[: idx + 1]
            break
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip(" ,.;:") + "…"


def _dedupe_non_empty(lines: list[str], *, limit: int = _MAX_LIST_ITEMS) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in lines:
        text = _sanitize_line(raw)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text[:_MAX_STRING_LEN])
        if len(out) >= limit:
            break
    return out


def _derive_follow_up_from_unresolved(unresolved: list[str], *, limit: int = 4) -> list[str]:
    out: list[str] = []
    for item in unresolved:
        text = _short_text(item, max_len=180)
        if not text:
            continue
        out.append(f"Уточнить на живом собеседовании: {text}")
        if len(out) >= limit:
            break
    return out


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


def _build_fallback_resolution_summary(user_payload: dict[str, Any]) -> dict[str, Any]:
    """Deterministic, human-readable fallback when LLM is unavailable."""
    qa_rows = user_payload.get("questionsAndAnswers")
    rows = qa_rows if isinstance(qa_rows, list) else []
    resolved: list[str] = []
    unresolved: list[str] = []
    new_info: list[str] = []
    follow_up: list[str] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        q_text = _short_text(str(row.get("questionText") or ""), max_len=140)
        r_desc = _short_text(str(row.get("reasonDescription") or ""), max_len=140)
        answer = _sanitize_line(str(row.get("answerText") or ""))
        if not answer:
            unresolved.append(
                f"По вопросу «{q_text or 'без названия'}» не хватает содержательного ответа."
            )
            continue

        answer_len = len(answer)
        if answer_len >= 120:
            if r_desc:
                resolved.append(f"Удалось уточнить: {r_desc}.")
            elif q_text:
                resolved.append(f"Кандидат дал развернутый ответ по теме «{q_text}».")
            else:
                resolved.append("Кандидат дал развернутый ответ по одному из уточняющих вопросов.")
            first = _first_sentence(answer, max_len=180)
            if first:
                new_info.append(first)
        elif answer_len >= 60:
            if q_text:
                resolved.append(f"Получено частичное уточнение по теме «{q_text}».")
            else:
                resolved.append("Получено частичное уточнение по одному из вопросов.")
            first = _first_sentence(answer, max_len=160)
            if first:
                new_info.append(first)
            unresolved.append(
                f"Ответ по теме «{q_text or 'уточняющий вопрос'}» требует большей конкретики."
            )
        else:
            unresolved.append(
                f"Ответ по теме «{q_text or 'уточняющий вопрос'}» слишком краткий, нужна дополнительная конкретика."
            )

    context = user_payload.get("interviewContext")
    issue_candidates = []
    if isinstance(context, dict) and isinstance(context.get("issue_candidates"), list):
        issue_candidates = [x for x in context.get("issue_candidates") if isinstance(x, dict)]
    for issue in issue_candidates[:8]:
        summary = _short_text(str(issue.get("summary") or ""), max_len=180)
        if not summary:
            continue
        severity = str(issue.get("severity") or "medium").lower()
        if severity == "high":
            follow_up.append(f"Проверить критичный момент: {summary}.")
        elif severity == "medium":
            follow_up.append(f"Уточнить важный момент: {summary}.")
        else:
            follow_up.append(f"При возможности уточнить: {summary}.")

    resolved = _dedupe_non_empty(resolved, limit=8)
    unresolved = _dedupe_non_empty(unresolved, limit=8)
    new_info = _dedupe_non_empty(new_info, limit=8)
    follow_up = _dedupe_non_empty(follow_up, limit=8)

    if not follow_up:
        follow_up = _derive_follow_up_from_unresolved(unresolved, limit=4)
    if not follow_up and resolved:
        follow_up = ["Проверить устойчивость и применимость озвученных примеров в реальных задачах обучения."]

    total_q = len([r for r in rows if isinstance(r, dict)])
    summary_parts: list[str] = []
    if total_q > 0:
        summary_parts.append(f"Кандидат завершил AI-собеседование и ответил на {total_q} вопросов.")
    if resolved:
        summary_parts.append(f"Удалось уточнить ключевые моменты: {resolved[0].rstrip('.')}.")
    if unresolved:
        summary_parts.append(f"Остаются вопросы для дополнительной проверки: {unresolved[0].rstrip('.')}.")
    if follow_up:
        summary_parts.append(f"На живом собеседовании стоит сфокусироваться на теме: {follow_up[0].rstrip('.')}.")
    short_summary = " ".join(summary_parts).strip() or "Кандидат завершил AI-собеседование; требуется уточнение отдельных деталей на живой встрече."

    if unresolved and len(unresolved) >= 2:
        confidence: Literal["low", "medium", "high"] = "low"
    elif unresolved:
        confidence = "medium"
    elif resolved:
        confidence = "high"
    else:
        confidence = "medium"

    now = datetime.now(tz=UTC)
    return {
        "shortSummary": short_summary[:_MAX_STRING_LEN],
        "resolvedPoints": resolved,
        "unresolvedPoints": unresolved,
        "newInformation": new_info,
        "followUpFocus": follow_up,
        "confidence": confidence,
        "generatedAt": now.isoformat(),
        "promptVersion": RESOLUTION_SUMMARY_PROMPT_VERSION,
        "generationSource": "fallback",
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
        f"followUpFocus (array with concrete follow-up topics for live interview, max {_MAX_LIST_ITEMS}), "
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
        "followUpFocus": parsed.followUpFocus or _derive_follow_up_from_unresolved(parsed.unresolvedPoints),
        "confidence": parsed.confidence,
        "generatedAt": now.isoformat(),
        "promptVersion": RESOLUTION_SUMMARY_PROMPT_VERSION,
        "generationSource": "llm",
    }
    return out


def try_generate_and_persist_resolution_summary(
    db: Session,
    application_id: UUID,
    row: AIInterviewQuestionSet,
) -> None:
    """Best-effort generation; always persists usable summary via fallback when needed."""
    if row.resolution_summary is not None:
        logger.info(
            "resolution_summary: skip generation (already present) application_id=%s session_id=%s",
            application_id,
            row.id,
        )
        return

    payload = _build_user_payload(db, application_id, row)
    try:
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
        fallback_summary = _build_fallback_resolution_summary(payload)
        row.resolution_summary = fallback_summary
        row.resolution_summary_error = safe[:2000]
        db.flush()
        audit_log_service.write_audit(
            db,
            entity_type="application",
            entity_id=application_id,
            action="ai_interview_resolution_summary_fallback_generated",
            actor_user_id=None,
            after_data={
                "session_id": str(row.id),
                "generated_at": fallback_summary.get("generatedAt"),
                "source": "fallback",
            },
        )


def ensure_resolution_summary_available(
    db: Session,
    *,
    application_id: UUID,
    row: AIInterviewQuestionSet | None = None,
) -> AIInterviewQuestionSet | None:
    """Backfill missing summary for completed interviews (non-raising best effort)."""
    target = row or ai_interview_repository.get_question_set_for_application(db, application_id)
    if not target:
        return None
    if target.candidate_completed_at is None:
        return target
    if isinstance(target.resolution_summary, dict):
        return target
    try_generate_and_persist_resolution_summary(db, application_id, target)
    db.refresh(target)
    return target
