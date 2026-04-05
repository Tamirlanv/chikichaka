"""Derive commission kanban card border hints (rubric completeness, stage-1 readiness)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.commission.application.section_score_service import SECTION_SCORE_CONFIGS
from invision_api.models.commission import SectionReviewScore
from invision_api.services.ai_interview.data_readiness import get_data_check_overall_status, is_data_processing_ready
_SECTION_TRIO = ("path", "motivation", "achievements")


def _required_manual_keys() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for section in _SECTION_TRIO:
        cfg = SECTION_SCORE_CONFIGS.get(section) or []
        out[section] = {str(c.get("key")) for c in cfg if c.get("key")}
    return out


def application_review_total_score(db: Session, application_id: UUID) -> int | None:
    """Total manual score for a complete reviewer on required stage-2 sections.

    We look for a reviewer who filled all required keys in:
    motivation + path + achievements. If multiple reviewers are complete,
    pick the most recently updated complete set.
    """
    required = _required_manual_keys()
    rows = db.scalars(
        select(SectionReviewScore).where(
            SectionReviewScore.application_id == application_id,
            SectionReviewScore.section.in_(_SECTION_TRIO),
            SectionReviewScore.manual_score.is_not(None),
        )
    ).all()
    if not rows:
        return None

    by_reviewer: dict[UUID, dict[str, dict[str, SectionReviewScore]]] = {}
    for row in rows:
        rid = row.reviewer_user_id
        by_reviewer.setdefault(rid, {}).setdefault(row.section, {})[row.score_key] = row

    complete: list[tuple[datetime, int]] = []
    epoch = datetime.fromtimestamp(0, tz=UTC)
    for _, sec_map in by_reviewer.items():
        total = 0
        latest = epoch
        ok = True
        for section in _SECTION_TRIO:
            needed_keys = required.get(section) or set()
            if not needed_keys:
                ok = False
                break
            scored = sec_map.get(section) or {}
            if not needed_keys.issubset(set(scored.keys())):
                ok = False
                break
            for key in needed_keys:
                score_row = scored[key]
                if score_row.manual_score is None:
                    ok = False
                    break
                total += int(score_row.manual_score)
                updated = score_row.updated_at or epoch
                if updated > latest:
                    latest = updated
            if not ok:
                break
        if ok:
            complete.append((latest, total))

    if not complete:
        return None
    complete.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return complete[0][1]


def rubric_three_sections_complete(db: Session, application_id: UUID) -> bool:
    """True if there is at least one complete manual scoring set for stage-2 trio."""
    return application_review_total_score(db, application_id) is not None


def stage_one_data_ready(db: Session, application_id: UUID, *, has_ai_summary: bool) -> bool:
    """Summary present and data-check aggregate status is ready."""
    if not has_ai_summary:
        return False
    return is_data_processing_ready(db, application_id)

def latest_data_check_run_status(db: Session, application_id: UUID) -> str | None:
    """Most recent data-check run aggregate status (``pending``/``running``/``ready``/...).

    Recomputed from per-unit checks (same as personal-info / AI readiness), not the run row alone.
    """
    return get_data_check_overall_status(db, application_id)
