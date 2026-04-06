"""Build compact context for AI interview question generation."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import Application, ApplicationReviewSnapshot
from invision_api.models.candidate_signals_aggregate import CandidateSignalsAggregate
from invision_api.repositories import data_check_repository

_SECTION_LABELS_RU: dict[str, str] = {
    "motivation_goals": "Мотивация",
    "motivation_letter": "Мотивация",
    "growth_journey": "Путь",
    "achievements_activities": "Достижения",
    "leadership_evidence": "Лидерство",
    "education": "Образование",
    "internal_test": "Тест",
}

_REASON_PRIORITIES: dict[str, int] = {
    "contradiction": 5,
    "authenticity_check": 4,
    "missing_context": 3,
    "low_concreteness": 2,
    "strong_signal_clarification": 1,
}

_SEVERITY_PRIORITIES: dict[str, int] = {"high": 3, "medium": 2, "low": 1}


def _section_payloads(app: Application) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in app.section_states:
        if isinstance(row.payload, dict):
            out[row.section_key] = row.payload
    return out


def _excerpt(text: str | None, max_len: int) -> str | None:
    if not text or not str(text).strip():
        return None
    s = str(text).strip()
    if len(s) <= max_len:
        return s
    return s[:max_len] + "…"


def _truncate_expl_dict(d: dict[str, Any], max_chars: int = 4000) -> dict[str, Any]:
    """Keep structure but cap total serialized size for LLM."""
    import json

    raw = json.dumps(d, ensure_ascii=False)
    if len(raw) <= max_chars:
        return d
    return {"_truncated": True, "preview": raw[:max_chars] + "…"}


def _section_label(section_key: str) -> str:
    return _SECTION_LABELS_RU.get(section_key, section_key)


def _extract_text_fragments(value: Any, *, out: list[str], cap: int = 120) -> None:
    if len(out) >= cap:
        return
    if isinstance(value, str):
        txt = " ".join(value.split()).strip()
        if txt:
            out.append(txt)
        return
    if isinstance(value, list):
        for item in value:
            _extract_text_fragments(item, out=out, cap=cap)
            if len(out) >= cap:
                return
        return
    if isinstance(value, dict):
        for item in value.values():
            _extract_text_fragments(item, out=out, cap=cap)
            if len(out) >= cap:
                return


def _payload_text_size(payload: dict[str, Any]) -> int:
    fragments: list[str] = []
    _extract_text_fragments(payload, out=fragments, cap=160)
    return sum(len(x) for x in fragments)


def _normalize_issue_text(text: str) -> str:
    txt = re.sub(r"\s+", " ", text).strip()
    return txt[:240]


def _normalize_severity(raw: Any) -> str:
    sev = str(raw or "").strip().lower()
    if sev in {"high", "высокий"}:
        return "high"
    if sev in {"low", "низкий"}:
        return "low"
    return "medium"


def _issue_score(issue: dict[str, Any]) -> int:
    reason = str(issue.get("reasonType") or "")
    severity = str(issue.get("severity") or "medium")
    return _REASON_PRIORITIES.get(reason, 0) * 10 + _SEVERITY_PRIORITIES.get(severity, 1)


def _collect_issue_candidates(
    *,
    sections: dict[str, dict[str, Any]],
    sig_summary: dict[str, Any],
    review_summary: dict[str, Any],
    ai_review_compact: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    dedupe: set[tuple[str, str, tuple[str, ...]]] = set()

    def push(
        *,
        reason_type: str,
        summary: str,
        severity: str = "medium",
        source_sections: list[str] | None = None,
    ) -> None:
        clean = _normalize_issue_text(summary)
        if len(clean) < 8:
            return
        sections_norm = [str(s).strip() for s in (source_sections or []) if str(s).strip()]
        key = (
            reason_type,
            clean.lower(),
            tuple(sorted(sections_norm)),
        )
        if key in dedupe:
            return
        dedupe.add(key)
        issues.append(
            {
                "reasonType": reason_type,
                "summary": clean,
                "severity": _normalize_severity(severity),
                "sourceSections": sections_norm[:4],
            }
        )

    # 1) Explicit contradictions from review snapshot.
    consistency_flags = review_summary.get("consistency_flags") or []
    if isinstance(consistency_flags, list):
        for flag in consistency_flags[:10]:
            if isinstance(flag, dict):
                text = (
                    flag.get("description")
                    or flag.get("message")
                    or flag.get("note")
                    or flag.get("title")
                    or flag.get("flag")
                    or ""
                )
                sections_hint = flag.get("sections") or flag.get("source_sections") or []
                if not isinstance(sections_hint, list):
                    sections_hint = []
                push(
                    reason_type="contradiction",
                    summary=f"Есть расхождение: {text}" if text else "Есть потенциальное расхождение между разделами.",
                    severity=_normalize_severity(flag.get("severity")),
                    source_sections=[str(s) for s in sections_hint],
                )
            elif isinstance(flag, str):
                push(
                    reason_type="contradiction",
                    summary=f"Есть расхождение: {flag}",
                    severity="medium",
                    source_sections=[],
                )

    # 2) Signals aggregate.
    for flag in list(sig_summary.get("attention_flags") or [])[:12]:
        if isinstance(flag, str) and flag.strip():
            push(
                reason_type="missing_context",
                summary=f"Нужно уточнение по материалам: {flag}",
                severity="medium",
                source_sections=[],
            )

    for flag in list(sig_summary.get("authenticity_concern_signals") or [])[:8]:
        if isinstance(flag, str) and flag.strip():
            push(
                reason_type="authenticity_check",
                summary=f"Нужна проверка достоверности формулировок: {flag}",
                severity="high",
                source_sections=[],
            )

    for item in list(sig_summary.get("explainability") or [])[:8]:
        if isinstance(item, str) and item.strip():
            push(
                reason_type="low_concreteness",
                summary=f"Недостаточно конкретики: {item}",
                severity="medium",
                source_sections=[],
            )

    # 3) AI review weak points / red flags.
    if isinstance(ai_review_compact, dict):
        for wp in list(ai_review_compact.get("weak_points") or [])[:8]:
            if isinstance(wp, str) and wp.strip():
                push(
                    reason_type="missing_context",
                    summary=f"Слабое место, требующее уточнения: {wp}",
                    severity="medium",
                    source_sections=[],
                )
        for rf in list(ai_review_compact.get("red_flags") or [])[:8]:
            if isinstance(rf, str) and rf.strip():
                push(
                    reason_type="authenticity_check",
                    summary=f"Спорный сигнал для проверки: {rf}",
                    severity="high",
                    source_sections=[],
                )

    # 4) Section completeness / concreteness heuristics.
    focus_sections = (
        "motivation_goals",
        "motivation_letter",
        "growth_journey",
        "achievements_activities",
        "leadership_evidence",
    )
    for key in focus_sections:
        payload = sections.get(key)
        if not isinstance(payload, dict):
            continue
        text_size = _payload_text_size(payload)
        if text_size < 120:
            push(
                reason_type="low_concreteness",
                summary=f"Раздел «{_section_label(key)}» раскрыт слишком кратко.",
                severity="medium",
                source_sections=[key],
            )

    growth_payload = sections.get("growth_journey")
    if isinstance(growth_payload, dict):
        answers = growth_payload.get("answers")
        strong_answers = 0
        if isinstance(answers, dict):
            for val in answers.values():
                if isinstance(val, dict):
                    txt = str(val.get("text") or "").strip()
                else:
                    txt = str(val or "").strip()
                if len(txt) >= 120:
                    strong_answers += 1
        if strong_answers < 2:
            push(
                reason_type="missing_context",
                summary="В разделе «Путь» мало развернутых ответов; нужны конкретные примеры действий и выводов.",
                severity="medium",
                source_sections=["growth_journey"],
            )

    ach_payload = sections.get("achievements_activities")
    if isinstance(ach_payload, dict):
        acts = ach_payload.get("activities")
        if not isinstance(acts, list) or len(acts) == 0:
            push(
                reason_type="missing_context",
                summary="В разделе «Достижения» не хватает подтвержденных примеров личного вклада.",
                severity="medium",
                source_sections=["achievements_activities"],
            )

    issues.sort(key=_issue_score, reverse=True)
    out: list[dict[str, Any]] = []
    for i, issue in enumerate(issues[:16]):
        out.append(
            {
                "id": f"issue_{i + 1}",
                **issue,
            }
        )
    return out


def build_interview_context(db: Session, application_id: UUID) -> dict[str, Any]:
    app = db.get(Application, application_id)
    if not app:
        raise ValueError("application not found")

    signals_row = db.scalars(
        select(CandidateSignalsAggregate).where(CandidateSignalsAggregate.application_id == application_id)
    ).first()

    snapshot = db.scalars(
        select(ApplicationReviewSnapshot).where(ApplicationReviewSnapshot.application_id == application_id)
    ).first()

    sections = _section_payloads(app)

    runs = data_check_repository.list_runs_for_application(db, application_id)
    data_check_summary: dict[str, Any] | None = None
    if runs:
        checks = data_check_repository.list_checks_for_run(db, runs[0].id)
        data_check_summary = {"units": [c.check_type for c in checks], "status_sample": checks[0].status if checks else None}

    sig_summary: dict[str, Any] = {}
    if signals_row:
        sig_summary = {
            "attention_flags": list(signals_row.attention_flags or []),
            "authenticity_concern_signals": list(signals_row.authenticity_concern_signals or []),
            "explainability": list(signals_row.explainability or [])[:20],
            "manual_review_required": signals_row.manual_review_required,
            "leadership_signals": signals_row.leadership_signals,
            "growth_signals": signals_row.growth_signals,
            "mission_fit_signals": signals_row.mission_fit_signals,
        }

    review_summary: dict[str, Any] = {}
    if snapshot:
        exp_sn = snapshot.explainability_snapshot
        review_summary = {
            "consistency_flags": snapshot.consistency_flags,
            "authenticity_risk_flag": snapshot.authenticity_risk_flag,
            "summary_by_block_keys": list((snapshot.summary_by_block or {}).keys())
            if isinstance(snapshot.summary_by_block, dict)
            else [],
            "explainability_snapshot": _truncate_expl_dict(exp_sn) if isinstance(exp_sn, dict) else None,
            "reviewer_notes_excerpt": _excerpt(snapshot.reviewer_notes_internal, 600),
            "ai_summary_draft_excerpt": _excerpt(snapshot.ai_summary_draft, 800),
        }

    ai_row = data_check_repository.latest_ai_review(db, application_id)
    ai_review_compact: dict[str, Any] | None = None
    if ai_row:
        fl = ai_row.flags if isinstance(ai_row.flags, dict) else {}
        ex_ai = ai_row.explainability_snapshot
        ai_review_compact = {
            "weak_points": list(fl.get("weak_points") or [])[:16],
            "red_flags": list(fl.get("red_flags") or [])[:16],
            "authenticity_risk_score": ai_row.authenticity_risk_score,
            "explainability_keys": list(ex_ai.keys())[:24] if isinstance(ex_ai, dict) else [],
        }

    issue_candidates = _collect_issue_candidates(
        sections=sections,
        sig_summary=sig_summary,
        review_summary=review_summary,
        ai_review_compact=ai_review_compact,
    )

    return {
        "application_id": str(application_id),
        "section_keys": list(sections.keys()),
        "sections_compact": {k: _truncate_section(k, v) for k, v in list(sections.items())[:12]},
        "signals": sig_summary,
        "review_snapshot": review_summary,
        "data_check": data_check_summary,
        "ai_review": ai_review_compact,
        "issue_candidates": issue_candidates,
    }


def _truncate_section(key: str, payload: dict[str, Any], max_chars: int = 1200) -> Any:
    """Limit payload size for LLM."""
    import json

    raw = json.dumps(payload, ensure_ascii=False)
    if len(raw) <= max_chars:
        return payload
    return {"_truncated": True, "section": key, "preview": raw[:max_chars] + "…"}
