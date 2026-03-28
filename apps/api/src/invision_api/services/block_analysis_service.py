"""LLM text analysis for blocks; never emits a final admission decision."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.core.config import get_settings
from invision_api.models.enums import AnalysisRunStatus
from invision_api.repositories import admissions_repository
from invision_api.services import scoring_exclusions
from invision_api.services.ai_provider import get_ai_provider


def run_motivation_analysis(
    db: Session,
    application_id: UUID,
    *,
    narrative_text: str,
    block_key: str = "motivation_goals",
) -> Any:
    if scoring_exclusions.should_exclude_block_for_scoring(block_key):
        return admissions_repository.create_text_analysis_run(
            db,
            application_id,
            block_key=block_key,
            source_kind="inline",
            source_document_id=None,
            model=None,
            status=AnalysisRunStatus.skipped.value,
            explanations={"reason": "block excluded from automated scoring"},
        )

    settings = get_settings()
    if not settings.openai_api_key:
        return admissions_repository.create_text_analysis_run(
            db,
            application_id,
            block_key=block_key,
            source_kind="inline",
            source_document_id=None,
            model=None,
            status=AnalysisRunStatus.skipped.value,
            explanations={"reason": "OPENAI_API_KEY not configured"},
        )

    provider = get_ai_provider()
    ctx = scoring_exclusions.filter_context_for_scoring({"narrative": narrative_text})
    notes = provider.explainability_flags(prompt_version="block_analysis_v1", context=ctx)
    return admissions_repository.create_text_analysis_run(
        db,
        application_id,
        block_key=block_key,
        source_kind="inline",
        source_document_id=None,
        model=settings.openai_model,
        status=AnalysisRunStatus.completed.value,
        dimensions={"clarity": None, "coherence": None},
        explanations=notes,
        flags={},
    )
