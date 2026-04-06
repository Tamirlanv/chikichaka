from types import SimpleNamespace
from uuid import uuid4

from invision_api.services.ai_interview import generation


def _context_with_issues() -> dict:
    return {
        "section_keys": ["growth_journey", "achievements_activities"],
        "sections_compact": {},
        "signals": {"attention_flags": ["нужна конкретика по роли"]},
        "issue_candidates": [
            {
                "id": "issue_1",
                "reasonType": "missing_context",
                "summary": "Не раскрыта личная роль в проекте OKU.",
                "severity": "medium",
                "sourceSections": ["achievements_activities"],
            },
            {
                "id": "issue_2",
                "reasonType": "contradiction",
                "summary": "Цели в мотивации не полностью совпадают с описанным опытом.",
                "severity": "high",
                "sourceSections": ["motivation_goals", "achievements_activities"],
            },
        ],
    }


def test_contextual_fallback_questions_use_issue_candidates() -> None:
    out = generation._fallback_questions(_context_with_issues(), 3)  # noqa: SLF001
    assert len(out) == 3
    assert all((q.get("generatedBy") or "").startswith("system_fallback") for q in out)
    joined = " ".join(str(q.get("questionText") or "") for q in out).lower()
    assert "оку" in joined or "роль" in joined
    assert "расхождение" in joined or "соглас" in joined


def test_generate_questions_llm_no_key_uses_contextual_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        "invision_api.services.ai_interview.generation.get_settings",
        lambda: SimpleNamespace(openai_api_key=None),
    )
    qs, meta = generation.generate_questions_llm(
        context=_context_with_issues(),
        target_count=3,
        application_id=uuid4(),
    )
    assert len(qs) == 3
    assert meta.get("path") == "fallback_contextual"
    assert meta.get("reason") == "no_openai_key"


def test_generate_questions_llm_fake_test_key_skips_openai_call(monkeypatch) -> None:
    monkeypatch.setattr(
        "invision_api.services.ai_interview.generation.get_settings",
        lambda: SimpleNamespace(openai_api_key="sk-test-fake"),
    )

    class _ProviderShouldNotBeCalled:
        def __init__(self) -> None:
            raise AssertionError("OpenAIProvider must not be initialized for placeholder key")

    monkeypatch.setattr(
        "invision_api.services.ai_interview.generation.OpenAIProvider",
        _ProviderShouldNotBeCalled,
    )

    qs, meta = generation.generate_questions_llm(
        context=_context_with_issues(),
        target_count=3,
        application_id=uuid4(),
    )
    assert len(qs) == 3
    assert meta.get("path") == "fallback_contextual"
    assert meta.get("reason") == "openai_test_key"
