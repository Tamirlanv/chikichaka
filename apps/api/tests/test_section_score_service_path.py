from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from invision_api.commission.application import section_score_service as sss


def _run_with(signals: dict[str, float], per_question: dict[str, dict], *, manual: bool = False):
    return SimpleNamespace(
        explanations={"section_signals": signals, "per_question": per_question},
        dimensions=None,
        flags={"manual_review_required": manual},
        source_kind="post_submit",
    )


def test_path_scores_contentful_non_spam_floor_to_three(monkeypatch):
    run = _run_with(
        {"initiative": 0.1, "resilience": 0.1, "growth": 0.1},
        {
            "q1": {"spam_check": {"ok": True}, "heuristics": {"action_score": 0.3, "reflection_score": 0.2, "concrete_score": 0.2}, "key_sentences": ["Кандидат запустил проект."]},
            "q2": {"spam_check": {"ok": True}, "heuristics": {"action_score": 0.2, "reflection_score": 0.2, "concrete_score": 0.2}, "key_sentences": ["Преодолел сложный период."]},
            "q3": {"spam_check": {"ok": True}, "heuristics": {"action_score": 0.25, "reflection_score": 0.2, "concrete_score": 0.15}, "key_sentences": ["Сделал выводы и изменил подход."]},
            "q4": {"spam_check": {"ok": True}, "heuristics": {"action_score": 0.2, "reflection_score": 0.2, "concrete_score": 0.2}, "key_sentences": ["Организовал работу команды."]},
            "q5": {"spam_check": {"ok": True}, "heuristics": {"action_score": 0.2, "reflection_score": 0.2, "concrete_score": 0.2}, "key_sentences": ["Регулярно применяет знания на практике."]},
        },
    )
    monkeypatch.setattr(sss, "_get_preferred_analysis_run", lambda *_a, **_k: run)
    scores = sss._compute_path_scores(db=None, application_id=uuid4())  # type: ignore[arg-type]
    assert scores["initiative"] >= 3
    assert scores["resilience"] >= 3
    assert scores["reflection_growth"] >= 3


def test_path_scores_allow_one_for_strong_negative(monkeypatch):
    run = _run_with(
        {"initiative": 0.05, "resilience": 0.05, "growth": 0.05},
        {
            "q1": {"spam_check": {"ok": False}, "heuristics": {"action_score": 0.0, "reflection_score": 0.0, "concrete_score": 0.0}, "key_sentences": []},
            "q2": {"spam_check": {"ok": False}, "heuristics": {"action_score": 0.0, "reflection_score": 0.0, "concrete_score": 0.0}, "key_sentences": []},
            "q3": {"spam_check": {"ok": True}, "heuristics": {"action_score": 0.0, "reflection_score": 0.0, "concrete_score": 0.0}, "key_sentences": []},
        },
        manual=True,
    )
    monkeypatch.setattr(sss, "_get_preferred_analysis_run", lambda *_a, **_k: run)
    scores = sss._compute_path_scores(db=None, application_id=uuid4())  # type: ignore[arg-type]
    assert min(scores.values()) == 1


def test_path_aggregate_floor_three_for_contentful_non_spam(monkeypatch):
    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    monkeypatch.setattr(
        sss,
        "compute_recommended_scores",
        lambda *_a, **_k: {"initiative": 2, "resilience": 2, "reflection_growth": 2},
    )
    monkeypatch.setattr(sss, "_get_preferred_analysis_run", lambda *_a, **_k: SimpleNamespace())
    monkeypatch.setattr(sss, "_path_quality_metrics", lambda *_a, **_k: (0.9, 0.8, False))
    monkeypatch.setattr(
        sss,
        "build_reviewer_facing_explanation",
        lambda *_a, **_k: "ok",
    )

    out = sss.get_section_scores(
        db,
        application_id=uuid4(),
        section="path",
        reviewer_user_id=uuid4(),
    )
    assert out["aggregateRecommendedScore"] == 3
