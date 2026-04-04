"""Build compact context for AI interview question generation."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import Application, ApplicationReviewSnapshot
from invision_api.models.candidate_signals_aggregate import CandidateSignalsAggregate
from invision_api.repositories import data_check_repository


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

    return {
        "application_id": str(application_id),
        "section_keys": list(sections.keys()),
        "sections_compact": {k: _truncate_section(k, v) for k, v in list(sections.items())[:12]},
        "signals": sig_summary,
        "review_snapshot": review_summary,
        "data_check": data_check_summary,
        "ai_review": ai_review_compact,
    }


def _truncate_section(key: str, payload: dict[str, Any], max_chars: int = 1200) -> Any:
    """Limit payload size for LLM."""
    import json

    raw = json.dumps(payload, ensure_ascii=False)
    if len(raw) <= max_chars:
        return payload
    return {"_truncated": True, "section": key, "preview": raw[:max_chars] + "…"}
