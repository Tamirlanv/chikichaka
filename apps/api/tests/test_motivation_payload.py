from pydantic import ValidationError

from invision_api.services.section_payloads import MotivationGoalsSectionPayload


def test_motivation_payload_min_boundary() -> None:
    payload = MotivationGoalsSectionPayload.model_validate(
        {
            "narrative": "x" * 350,
            "was_pasted": False,
            "paste_count": 0,
            "last_pasted_at": None,
        }
    )
    assert len(payload.narrative) == 350
    assert payload.was_pasted is False
    assert payload.paste_count == 0


def test_motivation_payload_max_boundary() -> None:
    payload = MotivationGoalsSectionPayload.model_validate(
        {
            "narrative": "x" * 1000,
            "was_pasted": True,
            "paste_count": 2,
            "last_pasted_at": "2026-03-30T12:00:00Z",
        }
    )
    assert len(payload.narrative) == 1000
    assert payload.was_pasted is True
    assert payload.paste_count == 2
    assert payload.last_pasted_at is not None


def test_motivation_payload_rejects_too_short() -> None:
    try:
        MotivationGoalsSectionPayload.model_validate({"narrative": "x" * 349})
    except ValidationError as exc:
        assert "String should have at least 350 characters" in str(exc)
    else:
        raise AssertionError("Expected validation error for too-short narrative")


def test_motivation_payload_rejects_too_long() -> None:
    try:
        MotivationGoalsSectionPayload.model_validate({"narrative": "x" * 1001})
    except ValidationError as exc:
        assert "String should have at most 1000 characters" in str(exc)
    else:
        raise AssertionError("Expected validation error for too-long narrative")
