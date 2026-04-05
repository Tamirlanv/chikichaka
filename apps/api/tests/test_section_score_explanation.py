"""Tests for reviewer-facing recommended score explanations."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from invision_api.commission.application import section_score_explanation as sse


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


def test_build_reviewer_facing_explanation_no_tech_phrases_has_structure(
    mock_db: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_id = uuid4()
    items = [
        {
            "key": "motivation_level",
            "label": "Мотивированность",
            "recommendedScore": 4,
            "manualScore": None,
            "effectiveScore": 4,
        },
        {
            "key": "choice_awareness",
            "label": "Осознанность выбора",
            "recommendedScore": 3,
            "manualScore": None,
            "effectiveScore": 3,
        },
        {
            "key": "specificity",
            "label": "Конкретика",
            "recommendedScore": 5,
            "manualScore": None,
            "effectiveScore": 5,
        },
    ]
    monkeypatch.setattr(sse, "_fetch_analysis_run", lambda *_a, **_k: None)
    monkeypatch.setattr(sse, "get_validated_section", lambda *_a, **_k: None)

    text = sse.build_reviewer_facing_explanation(mock_db, app_id, "motivation", items, 4)
    lower = text.casefold()

    assert "итог:" in lower
    assert "рекомендуемая оценка:" in lower
    assert "средн" not in lower
    assert "округл" not in lower
    assert "максимум из тр" not in lower

    for bad in (
        "плотность",
        "словар",
        "шаблон",
        "эвристик",
        "срабатыван",
        "агрегирован",
        "структурные маркеры",
        "шкала 0",
    ):
        assert bad not in lower, f"unexpected technical fragment {bad!r} in {text!r}"


def test_path_explanation_avoids_numeric_scales_and_debug_phrases(
    mock_db: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_id = uuid4()
    items = [
        {
            "key": "initiative",
            "label": "Инициативность",
            "recommendedScore": 4,
            "manualScore": None,
            "effectiveScore": 4,
        },
        {
            "key": "resilience",
            "label": "Устойчивость",
            "recommendedScore": 3,
            "manualScore": None,
            "effectiveScore": 3,
        },
        {
            "key": "reflection_growth",
            "label": "Рефлексия и рост",
            "recommendedScore": 4,
            "manualScore": None,
            "effectiveScore": 4,
        },
    ]
    run = MagicMock()
    run.explanations = {
        "section_signals": {"initiative": 0.55, "resilience": 0.4, "growth": 0.42},
        "llm_summary": None,
    }
    run.dimensions = None

    def _fetch(db, aid, bk):  # noqa: ANN001
        if bk == "growth_journey":
            return run
        return None

    monkeypatch.setattr(sse, "_fetch_preferred_analysis_run", _fetch)
    monkeypatch.setattr(sse, "get_validated_section", lambda *_a, **_k: None)

    text = sse.build_reviewer_facing_explanation(mock_db, app_id, "path", items, 4)
    lower = text.casefold()
    assert "итог:" in lower
    assert "0." not in text
    assert "шкала" not in lower
    assert "эвристик" not in lower
    assert "агрегирован" not in lower


def test_path_explanation_uses_answers_first_and_filters_english_llm(
    mock_db: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_id = uuid4()
    items = [
        {"key": "initiative", "label": "Инициативность", "recommendedScore": 4, "manualScore": None, "effectiveScore": 4},
        {"key": "resilience", "label": "Устойчивость", "recommendedScore": 3, "manualScore": None, "effectiveScore": 3},
        {"key": "reflection_growth", "label": "Рефлексия и рост", "recommendedScore": 4, "manualScore": None, "effectiveScore": 4},
    ]
    run = MagicMock()
    run.explanations = {
        "section_signals": {"initiative": 0.72, "resilience": 0.48, "growth": 0.66},
        "llm_summary": "The applicant's materials include responses to five questions. Data unavailable.",
        "per_question": {},
    }
    run.dimensions = None
    run.source_kind = "post_submit"

    class _Answer:
        def __init__(self, text: str) -> None:
            self.text = text

    class _Validated:
        answers = {
            "q1": _Answer("Я самостоятельно запустил проект OKU и взял на себя структуру командной работы."),
            "q2": _Answer("Преодолел внутреннюю неуверенность и начал завершать проекты."),
            "q3": _Answer("Понял, что рост требует дисциплины и обратной связи."),
            "q4": _Answer("В сложные периоды продолжал работать по плану и анализировать ошибки."),
            "q5": _Answer("Изменил подход к обучению: знания применяю в реальных задачах."),
        }

    monkeypatch.setattr(sse, "_fetch_preferred_analysis_run", lambda *_a, **_k: run)
    monkeypatch.setattr(sse, "get_validated_section", lambda *_a, **_k: _Validated())

    text = sse.build_reviewer_facing_explanation(mock_db, app_id, "path", items, 4)
    lower = text.casefold()
    assert "the applicant" not in lower
    assert "data unavailable" not in lower
    assert "инициативность:" in lower
    assert "устойчивость:" in lower
    assert "рефлексия и рост:" in lower
    assert "проект oku" in lower or "проект oku" in lower
    assert "рекомендуемая оценка: 4" in lower


def test_path_intro_is_multiline_and_full_labels(
    mock_db: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_id = uuid4()
    items = [
        {"key": "initiative", "label": "Инициативность", "recommendedScore": 3, "manualScore": None, "effectiveScore": 3},
        {"key": "resilience", "label": "Устойчивость", "recommendedScore": 3, "manualScore": None, "effectiveScore": 3},
        {"key": "reflection_growth", "label": "Рефлексия и рост", "recommendedScore": 3, "manualScore": None, "effectiveScore": 3},
    ]
    run = MagicMock()
    run.explanations = {"section_signals": {"initiative": 0.4, "resilience": 0.4, "growth": 0.4}, "per_question": {}}
    run.dimensions = None
    run.source_kind = "post_submit"
    monkeypatch.setattr(sse, "_fetch_preferred_analysis_run", lambda *_a, **_k: run)
    monkeypatch.setattr(sse, "get_validated_section", lambda *_a, **_k: None)

    text = sse.build_reviewer_facing_explanation(mock_db, app_id, "path", items, 3)
    assert "Для раздела «Путь» рассчитаны рекомендованные баллы:" in text
    assert "«Инициативность» — 3" in text
    assert "«Устойчивость» — 3" in text
    assert "«Рефлексия и рост» — 3" in text
    assert "«Рефлексия..." not in text


def test_path_explanation_without_evidence_does_not_use_llm_summary(
    mock_db: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_id = uuid4()
    items = [
        {"key": "initiative", "label": "Инициативность", "recommendedScore": 2, "manualScore": None, "effectiveScore": 2},
        {"key": "resilience", "label": "Устойчивость", "recommendedScore": 2, "manualScore": None, "effectiveScore": 2},
        {"key": "reflection_growth", "label": "Рефлексия и рост", "recommendedScore": 2, "manualScore": None, "effectiveScore": 2},
    ]
    run = MagicMock()
    run.explanations = {
        "section_signals": {"initiative": 0.1, "resilience": 0.1, "growth": 0.1},
        "llm_summary": "The applicant's materials include responses to five questions. Data unavailable.",
        "per_question": {},
    }
    run.dimensions = None
    run.source_kind = "post_submit"
    monkeypatch.setattr(sse, "_fetch_preferred_analysis_run", lambda *_a, **_k: run)
    monkeypatch.setattr(sse, "get_validated_section", lambda *_a, **_k: None)

    text = sse.build_reviewer_facing_explanation(mock_db, app_id, "path", items, 2)
    lower = text.casefold()
    assert "the applicant" not in lower
    assert "data unavailable" not in lower
    assert "недостаточно фактов для уверенного вывода" in lower
