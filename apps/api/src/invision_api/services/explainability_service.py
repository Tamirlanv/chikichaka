"""Aggregate explainability snapshots from analysis runs (respects scoring exclusions)."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import TextAnalysisRun
from invision_api.services import scoring_exclusions


def build_explainability_snapshot(db: Session, application_id: UUID) -> dict[str, Any]:
    runs = list(
        db.scalars(
            select(TextAnalysisRun)
            .where(TextAnalysisRun.application_id == application_id)
            .order_by(TextAnalysisRun.created_at.desc())
        ).all()
    )
    by_block: dict[str, Any] = {}
    for r in runs:
        if scoring_exclusions.should_exclude_block_for_scoring(r.block_key):
            continue
        if r.block_key not in by_block:
            by_block[r.block_key] = {
                "status": r.status,
                "explanations": r.explanations,
                "dimensions": r.dimensions,
            }
    return {"by_block": by_block, "run_count_considered": len(by_block)}
