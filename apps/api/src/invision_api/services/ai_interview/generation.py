"""LLM + fallback generation for clarification interview questions."""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any
from uuid import UUID

from invision_api.core.config import get_settings
from invision_api.services.ai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


def build_ai_interview_questions_openai_messages(
    *, context: dict[str, Any], target_count: int
) -> tuple[str, str]:
    """Exact (system, user) strings passed to committee_structured_summary for question generation."""
    system = (
        "You generate clarification interview questions for university admissions (Russian). "
        "Questions must be tied to THIS applicant's materials only and must be issue-driven. "
        "Primary source is context.issue_candidates (contradictions, weak points, missing context). "
        "Never produce generic questions detached from issue_candidates when issue_candidates is non-empty. "
        "Each question MUST reference at least one section key from context.section_keys or context.sections_compact "
        "in the sourceSections array (use exact keys as listed). "
        "Distribute questions across different issue_candidates; avoid duplicates. "
        "Tone: neutral, respectful, not accusatory. Never say 'explain the contradiction'. "
        "Ask for concrete examples, role, decisions, consistency. "
        "Do not include internal pipeline field names, JSON keys, or debugging labels in questionText. "
        f"Return exactly {target_count} questions as JSON object with key 'questions' — array of objects: "
        "questionText (ru), reasonType (one of: contradiction, low_concreteness, authenticity_check, "
        "missing_context, strong_signal_clarification), reasonDescription (ru, short), "
        "sourceSections (array of section keys from context), severity (low|medium|high), "
        "issueId (optional string, id from context.issue_candidates when applicable)."
    )
    user = json.dumps({"targetCount": target_count, "context": context}, ensure_ascii=False)[:80000]
    return system, user


REASON_TYPES = (
    "contradiction",
    "low_concreteness",
    "authenticity_check",
    "missing_context",
    "strong_signal_clarification",
)

# Substrings that must not appear in candidate-facing questionText (LLM leakage / schema echo).
_QUESTION_TEXT_FORBIDDEN = (
    "reasonDescription",
    "sourceSections",
    "commissionEdited",
    "questionText",
    "growth_journey",
    "achievements_activities",
    "motivation_letter",
    "motivation_goals",
    "internal_test",
    "JSON",
)


def _sanitize_question_text(text: str, *, idx: int) -> tuple[str, bool]:
    """Returns (cleaned text, True if content was altered or replaced)."""
    t = (text or "").strip()
    degraded = False
    lower = t.lower()
    for s in _QUESTION_TEXT_FORBIDDEN:
        if s.lower() in lower:
            degraded = True
            t = t.replace(s, "")
            t = t.replace(s.lower(), "")
            t = t.replace(s.upper(), "")
    t = " ".join(t.split())
    if len(t) < 12:
        degraded = True
        t = f"Уточните, пожалуйста, детали вашей заявки (вопрос {idx + 1})."
    return t[:2000], degraded


def _normalize_question(raw: dict[str, Any], idx: int) -> dict[str, Any]:
    qid = str(raw.get("id") or uuid.uuid4())
    rt = str(raw.get("reasonType") or "missing_context")
    if rt not in REASON_TYPES:
        rt = "missing_context"
    sev = str(raw.get("severity") or "medium").lower()
    if sev not in ("low", "medium", "high"):
        sev = "medium"
    text = (raw.get("questionText") or raw.get("text") or "").strip()
    if not text:
        text = f"Уточните, пожалуйста, мотивацию выбора программы (вопрос {idx + 1})."
    text, sanitized_leak = _sanitize_question_text(text, idx=idx)
    out: dict[str, Any] = {
        "id": qid,
        "questionText": text[:2000],
        "reasonType": rt,
        "reasonDescription": str(raw.get("reasonDescription") or "")[:2000],
        "sourceSections": list(raw.get("sourceSections") or [])[:16],
        "severity": sev,
        "generatedBy": str(raw.get("generatedBy") or "llm"),
        "isEditedByCommission": False,
        "isApproved": False,
        "sortOrder": idx,
    }
    issue_id = str(raw.get("issueId") or "").strip()
    if issue_id:
        out["issueId"] = issue_id[:64]
    if sanitized_leak:
        out["_questionTextSanitized"] = True
    return out


def _ensure_source_sections_linked(context: dict[str, Any], questions: list[dict[str, Any]]) -> None:
    """If sections exist in context but a question has no sourceSections, add a hint (explainability)."""
    keys = context.get("section_keys")
    if not isinstance(keys, list) or not keys:
        return
    for q in questions:
        ss = q.get("sourceSections") or []
        if not ss and isinstance(q.get("reasonDescription"), str):
            q["reasonDescription"] = (
                (q["reasonDescription"] + " " if q["reasonDescription"] else "")
                + f"(Привязка к разделам: укажите контекст из доступных секций: {', '.join(str(k) for k in keys[:8])}.)"
            ).strip()


def generate_questions_llm(
    *, context: dict[str, Any], target_count: int, application_id: UUID | str | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Returns (questions, meta) where meta includes path and degraded flag."""
    meta: dict[str, Any] = {"path": "llm", "degraded": False}
    settings = get_settings()
    api_key = (settings.openai_api_key or "").strip()
    key_lc = api_key.lower()
    placeholder_key = api_key.startswith("sk-test") or "test-fake" in key_lc or key_lc in {"fake", "none", "null"}
    if not api_key:
        logger.info("ai_interview: using fallback (no OPENAI_API_KEY)")
        qs = _fallback_questions(context, target_count)
        meta = {"path": "fallback_contextual", "degraded": True, "reason": "no_openai_key"}
        _ensure_source_sections_linked(context, qs)
        return qs, meta
    if placeholder_key:
        logger.info("ai_interview: using fallback (test/fake OPENAI key)")
        qs = _fallback_questions(context, target_count)
        meta = {"path": "fallback_contextual", "degraded": True, "reason": "openai_test_key"}
        _ensure_source_sections_linked(context, qs)
        return qs, meta

    try:
        provider = OpenAIProvider()
    except RuntimeError as e:
        logger.warning("ai_interview: OpenAI provider init failed: %s", e)
        qs = _fallback_questions(context, target_count)
        meta = {"path": "fallback_contextual", "degraded": True, "reason": "openai_init_failed"}
        _ensure_source_sections_linked(context, qs)
        return qs, meta

    system, user = build_ai_interview_questions_openai_messages(context=context, target_count=target_count)
    t0 = time.perf_counter()
    try:
        out = provider.committee_structured_summary(
            prompt_version="ai_interview_v1",
            compact_payload={},
            system_prompt=system,
            user_message=user,
            snapshot_flow="ai_interview_question_generation",
            snapshot_application_id=str(application_id) if application_id is not None else "",
        )
    except Exception as e:
        logger.warning("ai_interview: LLM call failed, using fallback: %s", e)
        qs = _fallback_questions(context, target_count)
        meta = {"path": "fallback_contextual", "degraded": True, "reason": "llm_error", "error": str(e)[:200]}
        _ensure_source_sections_linked(context, qs)
        return qs, meta

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    meta["llm_latency_ms"] = elapsed_ms
    logger.info("ai_interview: LLM ok in %sms, target_count=%s", elapsed_ms, target_count)

    raw_list = out.get("questions") if isinstance(out, dict) else None
    if not isinstance(raw_list, list) or not raw_list:
        logger.info("ai_interview: empty LLM questions, fallback")
        qs = _fallback_questions(context, target_count)
        meta = {
            "path": "fallback_contextual",
            "degraded": True,
            "reason": "empty_llm_response",
            "llm_latency_ms": elapsed_ms,
        }
        _ensure_source_sections_linked(context, qs)
        return qs, meta

    normalized = [_normalize_question(q, i) for i, q in enumerate(raw_list[:target_count])]
    while len(normalized) < target_count:
        normalized.append(_normalize_question({}, len(normalized)))
    any_san = any(q.pop("_questionTextSanitized", None) for q in normalized)
    if any_san:
        meta["degraded"] = True
        meta["question_text_sanitized"] = True
    _ensure_source_sections_linked(context, normalized)
    return normalized[:target_count], meta


def _fallback_questions(context: dict[str, Any], n: int) -> list[dict[str, Any]]:
    """Context-aware fallback when LLM unavailable."""
    raw_issues = context.get("issue_candidates")
    issues: list[dict[str, Any]] = []
    if isinstance(raw_issues, list):
        for raw in raw_issues:
            if not isinstance(raw, dict):
                continue
            summary = str(raw.get("summary") or "").strip()
            if not summary:
                continue
            issues.append(
                {
                    "id": str(raw.get("id") or f"issue_{len(issues) + 1}"),
                    "summary": summary[:220],
                    "reasonType": str(raw.get("reasonType") or "missing_context"),
                    "severity": str(raw.get("severity") or "medium"),
                    "sourceSections": [str(s) for s in list(raw.get("sourceSections") or [])[:4]],
                }
            )

    if not issues:
        section_keys = [str(k) for k in list(context.get("section_keys") or []) if str(k).strip()]
        for i, key in enumerate(section_keys[:8]):
            issues.append(
                {
                    "id": f"section_{i + 1}",
                    "summary": f"Нужно уточнить фактические детали по разделу «{key}».",
                    "reasonType": "missing_context",
                    "severity": "medium",
                    "sourceSections": [key],
                }
            )

    if not issues:
        issues = [
            {
                "id": "generic_1",
                "summary": "Нужно уточнить фактические детали заявки и личный вклад кандидата.",
                "reasonType": "missing_context",
                "severity": "medium",
                "sourceSections": [],
            }
        ]

    def build_text(issue: dict[str, Any], idx: int) -> tuple[str, str]:
        summary = str(issue.get("summary") or "Нужно уточнение").strip().rstrip(".")
        reason_type = str(issue.get("reasonType") or "missing_context")
        if reason_type == "contradiction":
            text = f"В материалах видно возможное расхождение: {summary}. Уточните, как это согласуется между разделами заявки."
            reason = "Проверка согласованности фактов и формулировок."
        elif reason_type == "authenticity_check":
            text = f"Уточните фактические детали по пункту: {summary}. Приведите конкретные подтверждающие примеры и вашу личную роль."
            reason = "Проверка достоверности и конкретности заявленных фактов."
        elif reason_type == "low_concreteness":
            text = f"В ответах не хватает конкретики по теме: {summary}. Опишите один конкретный кейс: ваши действия, результат и вывод."
            reason = "Уточнение конкретного действия и результата."
        elif reason_type == "strong_signal_clarification":
            text = f"Вы заявляете сильный сигнал по теме: {summary}. Раскройте его на примере: что сделали лично вы и как измерили результат."
            reason = "Подтверждение сильного сигнала фактическим примером."
        else:
            text = f"Раскройте подробнее тему: {summary}. Что именно произошло, какие решения вы приняли и к чему это привело?"
            reason = "Нужно добрать контекст по материалам заявки."
        return text[:2000], reason

    out: list[dict[str, Any]] = []
    used_issue_ids: set[str] = set()
    cursor = 0
    while len(out) < n and cursor < len(issues):
        issue = issues[cursor]
        cursor += 1
        issue_id = str(issue.get("id") or "")
        if issue_id in used_issue_ids:
            continue
        used_issue_ids.add(issue_id)
        text, reason = build_text(issue, len(out))
        out.append(
            _normalize_question(
                {
                    "id": str(uuid.uuid4()),
                    "issueId": issue_id,
                    "questionText": text,
                    "reasonType": issue.get("reasonType") or "missing_context",
                    "reasonDescription": reason,
                    "sourceSections": issue.get("sourceSections") or [],
                    "severity": issue.get("severity") or "medium",
                    "generatedBy": "system_fallback_contextual",
                },
                len(out),
            )
        )

    while len(out) < n:
        issue = issues[len(out) % len(issues)]
        text, reason = build_text(issue, len(out))
        out.append(
            _normalize_question(
                {
                    "id": str(uuid.uuid4()),
                    "issueId": issue.get("id"),
                    "questionText": text,
                    "reasonType": issue.get("reasonType") or "missing_context",
                    "reasonDescription": reason,
                    "sourceSections": issue.get("sourceSections") or [],
                    "severity": issue.get("severity") or "medium",
                    "generatedBy": "system_fallback_contextual",
                },
                len(out),
            )
        )
    return out[:n]
