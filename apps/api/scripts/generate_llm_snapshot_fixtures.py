#!/usr/bin/env python3
"""
Emit sample LLM snapshot JSON files (mocked OpenAI — no network, no DB).

Usage (from apps/api):

  cd apps/api && \\
    EXPORT_LLM_INPUT_SNAPSHOTS=1 \\
    OPENAI_API_KEY=sk-test-fake \\
    PYTHONPATH=src \\
    python scripts/generate_llm_snapshot_fixtures.py

Uses a fixed application_id placeholder. For real candidate text, run the platform
with EXPORT_LLM_INPUT_SNAPSHOTS=1 and trigger the real flows.
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import MagicMock

os.environ["EXPORT_LLM_INPUT_SNAPSHOTS"] = "1"
if not os.environ.get("OPENAI_API_KEY", "").strip():
    os.environ["OPENAI_API_KEY"] = "sk-test-fake"


def _install_cwd() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)


def main() -> None:
    _install_cwd()
    from invision_api.services.ai_provider import OpenAIProvider

    application_id = "00000000-0000-0000-0000-000000000001"
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content=json.dumps({"_fixture": True})))]

    provider = OpenAIProvider()
    provider._client.chat.completions.create = MagicMock(return_value=mock_resp)

    provider.committee_structured_summary(
        prompt_version="fixture_pv",
        compact_payload={},
        system_prompt="fixture system",
        user_message=json.dumps({"prompt_version": "fixture_pv", "payload": {}}, ensure_ascii=False),
        snapshot_flow="commission_structured_summary",
        snapshot_application_id=application_id,
    )
    provider.committee_structured_summary(
        prompt_version="ai_interview_v1",
        compact_payload={},
        system_prompt="fixture interview system",
        user_message=json.dumps({"targetCount": 3, "context": {"_": "fixture"}}, ensure_ascii=False),
        snapshot_flow="ai_interview_question_generation",
        snapshot_application_id=application_id,
    )
    provider.committee_structured_summary(
        prompt_version="resolution_summary_v1",
        compact_payload={},
        system_prompt="fixture resolution system",
        user_message=json.dumps({"interviewContext": {}, "questionsAndAnswers": []}, ensure_ascii=False),
        snapshot_flow="ai_interview_resolution_summary",
        snapshot_application_id=application_id,
    )
    print(
        f"Wrote snapshots under input_data_LLM/ for application_id={application_id}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
