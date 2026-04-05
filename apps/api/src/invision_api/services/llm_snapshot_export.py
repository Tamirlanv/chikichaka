"""Write exact OpenAI Chat Completions request snapshots to disk for external LLM testing.

Enabled only when environment variable EXPORT_LLM_INPUT_SNAPSHOTS=1.
Files go to apps/api/input_data_LLM/ by default (override with LLM_INPUT_SNAPSHOT_DIR).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


_EXPORT_ENV = "EXPORT_LLM_INPUT_SNAPSHOTS"
_DIR_ENV = "LLM_INPUT_SNAPSHOT_DIR"

_FLOW_TO_BASENAME = {
    "commission_structured_summary": "commission-structured-summary",
    "ai_interview_question_generation": "ai-interview-question-generation",
    "ai_interview_resolution_summary": "ai-interview-resolution-summary",
}


def _default_snapshot_root() -> Path:
    # invision_api/services/llm_snapshot_export.py -> parents[3] == apps/api
    return Path(__file__).resolve().parents[3] / "input_data_LLM"


def snapshot_root() -> Path:
    override = os.environ.get(_DIR_ENV, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _default_snapshot_root()


def snapshots_enabled() -> bool:
    return os.environ.get(_EXPORT_ENV, "").strip() == "1"


def write_openai_chat_snapshot(
    *,
    flow: str,
    application_id: str,
    request: dict[str, Any],
) -> Path | None:
    """Persist one snapshot. Returns written path if exported, else None."""
    if not snapshots_enabled():
        return None
    base = _FLOW_TO_BASENAME.get(flow)
    if not base:
        return None
    root = snapshot_root()
    root.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in application_id)
    path = root / f"{base}-{safe_id}.json"
    doc = {
        "flow": flow,
        "application_id": application_id,
        "request": request,
    }
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
