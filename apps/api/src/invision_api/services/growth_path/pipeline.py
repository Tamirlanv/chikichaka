"""Orchestrate preprocessing, spam checks, LLM summary, and TextAnalysisRun.

Candidate-side saves run soft technical validation only (no content-quality
blocking).  Full quality analysis (spam, heuristics, signals) is stored for
commission use but never blocks the candidate.  The same analysis function is
reused post-submit for the definitive assessment.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.core.config import get_settings
from invision_api.models.enums import AnalysisRunStatus
from invision_api.repositories import admissions_repository
from invision_api.services.growth_path.config import GROWTH_QUESTION_ORDER
from invision_api.services.growth_path.key_sentences import extract_key_sentences
from invision_api.services.growth_path.llm_summary import summarize_growth_path_compact
from invision_api.services.growth_path.normalize import normalize_growth_text
from invision_api.services.growth_path.signals import aggregate_section_signals, build_per_question_block
from invision_api.services.growth_path.spam_rules import check_answer_spam
from invision_api.services.section_payloads import GrowthJourneySectionPayload

logger = logging.getLogger(__name__)


def analyze_growth_answers(validated: GrowthJourneySectionPayload) -> dict[str, Any]:
    """Pure analysis: normalize, spam-check, heuristics, key sentences, signals.

    Never raises — returns computed data including per-question spam flags.
    Suitable for both save-time enrichment and post-submit definitive analysis.
    """
    per_question: dict[str, dict[str, Any]] = {}
    compact_questions: dict[str, Any] = {}

    for qid in GROWTH_QUESTION_ORDER:
        raw = validated.answers[qid].text
        text = normalize_growth_text(raw)
        spam = check_answer_spam(text)
        block = build_per_question_block(qid=qid, normalized_text=text)
        keys = extract_key_sentences(text, max_sentences=2)
        per_question[qid] = {
            **block,
            "key_sentences": keys,
            "spam_check": {"ok": spam.ok, "reasons": list(spam.reasons)},
        }
        compact_questions[qid] = {
            "stats": block["stats"],
            "heuristics": block["heuristics"],
            "key_sentences": keys,
            "spam_check": {"ok": spam.ok, "reasons": list(spam.reasons)},
        }

    section_signals = aggregate_section_signals(per_question)
    computed_at = datetime.now(tz=UTC).isoformat()

    return {
        "computed_at": computed_at,
        "per_question": per_question,
        "compact_questions": compact_questions,
        "section_signals": section_signals,
    }


def process_growth_journey_save(
    db: Session,
    application_id: UUID,
    validated: GrowthJourneySectionPayload,
) -> dict[str, Any]:
    """Candidate-side save: soft technical validation only.

    Runs analysis and stores results for commission review, but never blocks
    the candidate with content-quality errors (no 422 for spam/low-effort).
    """
    analysis = analyze_growth_answers(validated)

    compact_llm: dict[str, Any] = {
        "version": 1,
        "computed_at": analysis["computed_at"],
        "section_signals": analysis["section_signals"],
        "questions": analysis["compact_questions"],
    }

    summary = summarize_growth_path_compact(compact_llm)

    computed: dict[str, Any] = {
        "computed_at": analysis["computed_at"],
        "per_question": analysis["per_question"],
        "section_signals": analysis["section_signals"],
        "llm_summary": summary or None,
    }

    settings = get_settings()
    model_name = settings.openai_api_key and settings.openai_model or None
    status_val = AnalysisRunStatus.completed.value if summary else AnalysisRunStatus.skipped.value

    admissions_repository.create_text_analysis_run(
        db,
        application_id,
        block_key="growth_journey",
        source_kind="inline",
        source_document_id=None,
        model=model_name,
        status=status_val,
        dimensions={"section_signals": analysis["section_signals"]},
        explanations={
            "llm_summary": summary,
            "structured_compact": compact_llm,
            "per_question": analysis["per_question"],
        },
        flags={"has_llm_summary": bool(summary)},
    )

    return computed


def run_post_submit_growth_analysis(
    db: Session,
    application_id: UUID,
    validated: GrowthJourneySectionPayload,
) -> dict[str, Any]:
    """Post-submit definitive analysis stored with source_kind='post_submit'.

    Called during initial screening to produce the authoritative quality
    assessment for commission review.
    """
    analysis = analyze_growth_answers(validated)

    compact_llm: dict[str, Any] = {
        "version": 1,
        "computed_at": analysis["computed_at"],
        "section_signals": analysis["section_signals"],
        "questions": analysis["compact_questions"],
    }

    summary = summarize_growth_path_compact(compact_llm)

    settings = get_settings()
    model_name = settings.openai_api_key and settings.openai_model or None
    status_val = AnalysisRunStatus.completed.value if summary else AnalysisRunStatus.skipped.value

    admissions_repository.create_text_analysis_run(
        db,
        application_id,
        block_key="growth_journey",
        source_kind="post_submit",
        source_document_id=None,
        model=model_name,
        status=status_val,
        dimensions={"section_signals": analysis["section_signals"]},
        explanations={
            "llm_summary": summary,
            "structured_compact": compact_llm,
            "per_question": analysis["per_question"],
        },
        flags={"has_llm_summary": bool(summary)},
    )

    return {**analysis, "llm_summary": summary or None}
