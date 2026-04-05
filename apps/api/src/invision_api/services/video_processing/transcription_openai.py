from __future__ import annotations

import logging
from pathlib import Path

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from invision_api.core.config import get_settings

logger = logging.getLogger(__name__)


class ASRTranscriptionError(RuntimeError):
    """Base class for ASR transcription failures."""


class ASRConfigError(ASRTranscriptionError):
    """Raised when ASR client cannot be initialized due to configuration."""


class ASRNetworkError(ASRTranscriptionError):
    """Raised when ASR request fails due to timeout/network issues."""


class ASRProviderError(ASRTranscriptionError):
    """Raised when ASR provider rejects request or returns provider-side error."""


def transcribe_audio_wav(wav_path: Path) -> tuple[str, float | None]:
    """Transcribe via OpenAI-compatible ASR API. Returns (text, confidence or None)."""
    settings = get_settings()
    api_key = settings.asr_api_key or settings.openai_api_key
    if not api_key:
        raise ASRConfigError("ASR ключ не настроен (ASR_API_KEY/OPENAI_API_KEY).")
    client = OpenAI(api_key=api_key, base_url=settings.asr_base_url)
    try:
        with wav_path.open("rb") as f:
            tr = client.audio.transcriptions.create(
                model=settings.asr_model,
                file=f,
                language="ru",
                timeout=settings.asr_timeout_seconds,
            )
        text = (getattr(tr, "text", None) or "").strip()
        return text, None
    except (APITimeoutError, APIConnectionError) as exc:
        raise ASRNetworkError(f"ASR недоступен: {exc}") from exc
    except APIStatusError as exc:
        raise ASRProviderError(f"ASR вернул ошибку статуса: {exc.status_code}") from exc
    except Exception as exc:
        logger.exception("whisper transcription failed")
        raise ASRProviderError(f"ASR ошибка: {exc}") from exc
