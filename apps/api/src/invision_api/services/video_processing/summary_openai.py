from __future__ import annotations

import logging

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from invision_api.core.config import get_settings

logger = logging.getLogger(__name__)


class SummaryGenerationError(RuntimeError):
    """Base class for summary generation failures."""


class SummaryConfigError(SummaryGenerationError):
    """Raised when LLM summary client configuration is missing."""


class SummaryProviderError(SummaryGenerationError):
    """Raised when summary provider fails."""


def summarize_transcript_ru(transcript: str) -> str:
    """5–6 sentences in Russian based on transcript only."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise SummaryConfigError("OPENAI_API_KEY не настроен для суммаризации.")
    t = transcript.strip()
    if len(t) < 30:
        return ""
    client = OpenAI(api_key=settings.openai_api_key)
    system = (
        "Ты помощник приёмной комиссии. Сделай краткое содержание видеопрезентации кандидата "
        "на русском языке: ровно 5 или 6 законченных предложений. "
        "Не добавляй технические детали, оценки и рекомендации по зачислению. "
        "Пиши нейтрально и по делу."
    )
    user = f"Транскрипт речи из видео:\n\n{t[:48000]}"
    try:
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
            timeout=90.0,
        )
        return (resp.choices[0].message.content or "").strip()
    except (APITimeoutError, APIConnectionError) as exc:
        raise SummaryProviderError(f"Сервис суммаризации недоступен: {exc}") from exc
    except APIStatusError as exc:
        raise SummaryProviderError(f"Сервис суммаризации вернул статус: {exc.status_code}") from exc
    except Exception as exc:
        logger.exception("LLM summary failed")
        raise SummaryProviderError(f"Ошибка суммаризации: {exc}") from exc
