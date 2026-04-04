from __future__ import annotations

import logging
from pathlib import Path

from openai import OpenAI

from invision_api.core.config import get_settings

logger = logging.getLogger(__name__)


def transcribe_audio_wav(wav_path: Path) -> tuple[str, float | None]:
    """Transcribe via OpenAI Whisper API. Returns (text, confidence or None)."""
    settings = get_settings()
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY missing; skipping transcription")
        return "", None
    client = OpenAI(api_key=settings.openai_api_key)
    try:
        with wav_path.open("rb") as f:
            tr = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="ru",
            )
        text = (getattr(tr, "text", None) or "").strip()
        return text, None
    except Exception:
        logger.exception("whisper transcription failed")
        return "", None
