"""Compute interview question count (3–5) from weighted signal summary."""

from __future__ import annotations

from typing import Any


def compute_signal_weight(summary: dict[str, Any]) -> int:
    """Higher weight => more questions needed."""
    w = 0
    contradictions = summary.get("contradictions") or []
    if isinstance(contradictions, list):
        for c in contradictions:
            if not isinstance(c, dict):
                continue
            sev = str(c.get("severity") or c.get("level") or "").lower()
            if sev in ("high", "высокий"):
                w += 2
            elif sev in ("medium", "средний"):
                w += 1
            else:
                w += 1
    flags = summary.get("attention_flags") or []
    if isinstance(flags, list):
        w += min(len(flags), 4)
    auth = summary.get("authenticity_concerns") or summary.get("authenticity_flags") or []
    if isinstance(auth, list):
        w += min(len(auth), 3)
    low_conc = summary.get("low_concreteness") or summary.get("vague_sections") or []
    if isinstance(low_conc, list):
        w += min(len(low_conc), 2)
    if summary.get("manual_review_required"):
        w += 2
    if summary.get("paste_risk") or summary.get("suspected_template"):
        w += 1
    return w


def question_count_from_weight(weight: int) -> int:
    if weight <= 4:
        return 3
    if weight <= 8:
        return 4
    return 5
