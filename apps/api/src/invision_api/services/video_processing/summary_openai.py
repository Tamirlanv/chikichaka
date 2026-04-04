from __future__ import annotations

import logging

from openai import OpenAI

from invision_api.core.config import get_settings

logger = logging.getLogger(__name__)


def summarize_transcript_ru(transcript: str) -> str:
    """5–6 sentences in Russian based on transcript only."""
    settings = get_settings()
    if not settings.openai_api_key:
        return ""
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
    except Exception:
        logger.exception("LLM summary failed")
        return ""
