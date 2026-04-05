from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.enums import AnalysisRunStatus, SectionKey
from invision_api.repositories import admissions_repository
from invision_api.services.data_check.contracts import UnitExecutionResult
from invision_api.services.data_check.utils import get_validated_section
from invision_api.services.motivation_heuristics import compute_motivation_signals


def _sentences(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"[.!?]+", text) if p.strip()]
    return parts


def run_motivation_processing(db: Session, *, application_id: UUID) -> UnitExecutionResult:
    validated = get_validated_section(
        db,
        application_id=application_id,
        section_key=SectionKey.motivation_goals,
    )
    if not validated:
        return UnitExecutionResult(
            status="failed",
            errors=["Motivation section is missing or invalid."],
            explainability=["Не удалось валидировать раздел мотивации."],
        )

    text = validated.narrative.strip()
    sentences = _sentences(text)
    summary = " ".join(sentences[:3])[:700]
    signals = compute_motivation_signals(text)
    words_count = int(signals.get("word_count") or 0)
    manual = words_count < 70
    explainability = [
        "Сигналы построены алгоритмически по плотности мотивационных/доказательных маркеров и осознанности выбора.",
        f"Текст содержит {words_count} слов и {len(sentences)} предложений.",
    ]
    if manual:
        explainability.append("Короткий текст мотивации — нужен ручной просмотр комиссией.")

    admissions_repository.create_text_analysis_run(
        db,
        application_id,
        block_key="motivation_goals",
        source_kind="post_submit",
        source_document_id=validated.motivation_document_id,
        model=None,
        status=AnalysisRunStatus.completed.value,
        dimensions=signals,
        explanations={"summary": summary, "signals": signals},
        flags={"manual_review_required": manual},
    )

    return UnitExecutionResult(
        status="manual_review_required" if manual else "completed",
        payload={"summary": summary, "signals": signals},
        explainability=explainability,
        manual_review_required=manual,
    )
