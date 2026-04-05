"""Lexical / pattern signals for motivation letter subcriteria.

Shared by post-submit processing and commission scoring so stored dimensions
and reviewer-facing scores stay aligned.
"""

from __future__ import annotations

import re
from typing import Any

_MOTIVATION_TERMS = ("цель", "мисси", "вклад", "помочь", "разв", "обществ")
_EVIDENCE_TERMS = ("пример", "проект", "инициатив", "достиг", "результат")

_INTRINSIC_MARKERS = (
    "хочу ",
    "хочу\n",
    "стрем",
    "мечта",
    "интересно",
    "важно для мен",
    "сам выбрал",
    "сама выбрала",
    "сам решил",
    "сама решила",
)
_EXTRINSIC_MARKERS = (
    "родител",
    "начальник",
    "попросил",
    "попросили",
    "настоял",
    "настояли",
    "должен был",
    "должна была",
    "заставил",
)

_CHOICE_PATTERN_RES = [
    re.compile(r"не\s+просто\b", re.IGNORECASE),
    re.compile(r"не\s+только\b", re.IGNORECASE),
    re.compile(r"\bа\s+именно\b", re.IGNORECASE),
    re.compile(r"\bименно\s+эта\b", re.IGNORECASE),
    re.compile(r"\bименно\s+этот\b", re.IGNORECASE),
    re.compile(r"в\s+отличие\s+от\b", re.IGNORECASE),
    re.compile(r"почему\s+именно\b", re.IGNORECASE),
    re.compile(r"почему\s+я\b", re.IGNORECASE),
    re.compile(r"выбрал[аи]?\s+(?:эту|этот|данн)", re.IGNORECASE),
]
_PROGRAM_FIT_TERMS = (
    "invision",
    "инвизион",
    "ценност",
    "мисс",
    "формат",
    "программ",
    "курс",
    "обучен",
    "сред",
    "сообществ",
    "культур",
    "трансформац",
    "развити",
)


def _sentences(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"[.!?]+", text) if p.strip()]


def compute_motivation_signals(text: str) -> dict[str, Any]:
    stripped = text.strip()
    words = [w for w in re.split(r"\s+", stripped) if w]
    lower = stripped.lower()
    sentences = _sentences(stripped)

    motivation_hits = sum(1 for term in _MOTIVATION_TERMS if term in lower)
    evidence_hits = sum(1 for term in _EVIDENCE_TERMS if term in lower)
    avg_sentence_len = (len(words) / len(sentences)) if sentences else 0.0

    choice_pattern_hits = sum(1 for rx in _CHOICE_PATTERN_RES if rx.search(stripped))
    program_fit_hits = sum(1 for t in _PROGRAM_FIT_TERMS if t in lower)

    intrinsic_hits = sum(1 for m in _INTRINSIC_MARKERS if m in lower)
    extrinsic_hits = sum(1 for m in _EXTRINSIC_MARKERS if m in lower)

    has_digits = bool(re.search(r"\d{2,4}", stripped))
    bullet_like = stripped.count("\n") + stripped.count("•") + stripped.count("- ")

    return {
        "motivation_density": round(min(1.0, motivation_hits / 4), 3),
        "evidence_density": round(min(1.0, evidence_hits / 4), 3),
        "avg_sentence_len": round(avg_sentence_len, 2),
        "word_count": len(words),
        "char_count": len(stripped),
        "choice_pattern_hits": choice_pattern_hits,
        "choice_reasoning_density": round(min(1.0, choice_pattern_hits / 3), 3),
        "program_fit_hits": program_fit_hits,
        "program_fit_density": round(min(1.0, program_fit_hits / 5), 3),
        "intrinsic_hits": intrinsic_hits,
        "extrinsic_hits": extrinsic_hits,
        "intrinsic_ratio": round(
            intrinsic_hits / (intrinsic_hits + extrinsic_hits + 1),
            3,
        ),
        "has_digits": has_digits,
        "structure_markers": min(5, bullet_like),
    }


def motivation_subscores_from_signals(s: dict[str, Any]) -> dict[str, int]:
    def clamp_int(v: int) -> int:
        return max(1, min(5, v))

    mot_density = float(s.get("motivation_density") or 0)
    intrinsic_ratio = float(s.get("intrinsic_ratio") or 0.5)
    blended_mot = min(1.0, mot_density * (0.65 + 0.35 * intrinsic_ratio))

    if blended_mot > 0.22:
        motivation_level = 5
    elif blended_mot > 0.16:
        motivation_level = 4
    elif blended_mot > 0.09:
        motivation_level = 3
    elif blended_mot > 0.04:
        motivation_level = 2
    else:
        motivation_level = 1

    wc = int(s.get("word_count") or 0)
    choice_r = float(s.get("choice_reasoning_density") or 0)
    prog_f = float(s.get("program_fit_density") or 0)
    semantic_choice = min(1.0, 0.55 * choice_r + 0.45 * prog_f)
    wc_norm = min(1.0, wc / 220.0)
    combined_choice = 0.42 * wc_norm + 0.58 * semantic_choice
    if semantic_choice >= 0.45 and wc < 90:
        combined_choice = max(combined_choice, 0.52)

    if combined_choice > 0.72:
        choice_awareness = 5
    elif combined_choice > 0.55:
        choice_awareness = 4
    elif combined_choice > 0.38:
        choice_awareness = 3
    elif combined_choice > 0.22:
        choice_awareness = 2
    else:
        choice_awareness = 1

    evidence = float(s.get("evidence_density") or 0)
    has_digits = bool(s.get("has_digits"))
    struct = int(s.get("structure_markers") or 0)
    concrete_boost = min(0.15, 0.05 * min(struct, 3)) + (0.08 if has_digits else 0)
    spec_core = min(1.0, evidence + concrete_boost)

    if spec_core > 0.18:
        specificity = 5
    elif spec_core > 0.12:
        specificity = 4
    elif spec_core > 0.06:
        specificity = 3
    elif spec_core > 0.025:
        specificity = 2
    else:
        specificity = 1

    return {
        "motivation_level": clamp_int(motivation_level),
        "choice_awareness": clamp_int(choice_awareness),
        "specificity": clamp_int(specificity),
    }
