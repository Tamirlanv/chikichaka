"""Motivation subcriteria heuristics: semantic choice vs word-count-only."""

from __future__ import annotations

from invision_api.services.motivation_heuristics import (
    compute_motivation_signals,
    motivation_subscores_from_signals,
)


def test_short_text_strong_choice_markers_can_score_choice_above_word_count_only() -> None:
    text = (
        "Не просто учёба — а именно эта программа inVision: ценности сообщества и формат важнее диплома. "
        "Хочу расти здесь, потому что миссия близка моим целям."
    )
    s = compute_motivation_signals(text)
    scores = motivation_subscores_from_signals(s)
    assert scores["choice_awareness"] >= 4
    assert s["choice_pattern_hits"] >= 1
    assert s["program_fit_hits"] >= 2


def test_compute_signals_has_distinct_choice_and_evidence() -> None:
    text = (
        "Пример: я запустил проект и достиг результата. Цель — развитие. "
        "Не только курс, а именно эта среда."
    )
    s = compute_motivation_signals(text)
    assert s["evidence_density"] > 0
    assert s["choice_reasoning_density"] > 0
