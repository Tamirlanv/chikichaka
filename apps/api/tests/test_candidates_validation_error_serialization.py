from __future__ import annotations

import pytest
from pydantic import ValidationError

from invision_api.api.v1.routes.candidates import _safe_validation_errors
from invision_api.services.section_payloads import GrowthJourneySectionPayload


def test_safe_validation_errors_converts_exception_ctx_to_string() -> None:
    with pytest.raises(ValidationError) as exc_info:
        GrowthJourneySectionPayload.model_validate(
            {
                "answers": {
                    "q1": {"text": "too short"},
                    "q2": {"text": "x" * 120},
                    "q3": {"text": "x" * 120},
                    "q4": {"text": "x" * 120},
                    "q5": {"text": "x" * 120},
                },
                "consent_privacy": True,
                "consent_parent": True,
            }
        )

    errors = _safe_validation_errors(exc_info.value)
    assert errors
    ctx = errors[0].get("ctx") or {}
    if "error" in ctx:
        assert isinstance(ctx["error"], str)
