"""Shared sanitizer for reviewer-facing text in commission UI."""

from __future__ import annotations

import re

_TECHNICAL_RESIDUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bq\d+\b", re.IGNORECASE),
    re.compile(r"data unavailable", re.IGNORECASE),
    re.compile(r"details unavailable", re.IGNORECASE),
    re.compile(r"submission includes responses", re.IGNORECASE),
    re.compile(r"\bspam_questions\b", re.IGNORECASE),
    re.compile(r"\bspam_check\b", re.IGNORECASE),
    re.compile(r"\bheuristics\b", re.IGNORECASE),
    re.compile(r"\baction_score\b", re.IGNORECASE),
    re.compile(r"\breflection_score\b", re.IGNORECASE),
    re.compile(r"\bjson\b", re.IGNORECASE),
    re.compile(r"\bpayload\b", re.IGNORECASE),
    re.compile(r"\bpipeline\b", re.IGNORECASE),
)


def strip_technical_residue(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^[\-\*\d\.\)\s]+", "", cleaned)
    for pattern in _TECHNICAL_RESIDUE_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    cleaned = cleaned.replace("Данные недоступны", "")
    cleaned = cleaned.replace("Детали недоступны", "")
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def split_sentences(text: str) -> list[str]:
    if not text:
        return []
    parts = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text) if s.strip()]
    return parts if parts else [text.strip()]


def truncate_sentence(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rstrip()
    if " " in cut:
        cut = cut[: cut.rfind(" ")].rstrip()
    return f"{cut}..."


def _first_marker_index(text: str, markers: tuple[str, ...]) -> tuple[int, int] | None:
    low = text.lower()
    first_idx = -1
    first_len = 0
    for marker in markers:
        idx = low.find(marker)
        if idx == -1:
            continue
        if first_idx == -1 or idx < first_idx:
            first_idx = idx
            first_len = len(marker)
    if first_idx < 0:
        return None
    return first_idx, first_len


def _expand_to_word_boundaries(text: str, start: int, end: int) -> tuple[int, int]:
    n = len(text)
    while start > 0 and not text[start - 1].isspace():
        start -= 1
    while end < n and not text[end].isspace():
        end += 1
    return max(0, start), min(n, end)


def centered_keyword_snippet(
    text: str,
    markers: tuple[str, ...],
    *,
    max_chars: int = 180,
) -> str:
    """
    Build a centered snippet around the earliest keyword marker.
    Falls back to regular truncation when marker is absent.
    """
    cleaned = strip_technical_residue(text)
    if not cleaned:
        return ""
    if len(cleaned) <= max_chars:
        return cleaned

    marker = _first_marker_index(cleaned, markers)
    if marker is None:
        return truncate_sentence(cleaned, max_chars)

    idx, marker_len = marker
    center = idx + max(1, marker_len // 2)
    half = max_chars // 2
    start = max(0, center - half)
    end = min(len(cleaned), start + max_chars)
    if end - start < max_chars and start > 0:
        start = max(0, end - max_chars)
    start, end = _expand_to_word_boundaries(cleaned, start, end)

    fragment = cleaned[start:end].strip()
    if fragment.count("«") != fragment.count("»"):
        fragment = fragment.replace("«", "").replace("»", "").strip()

    prefix = "... " if start > 0 else ""
    suffix = " ..." if end < len(cleaned) else ""
    return f"{prefix}{fragment}{suffix}".strip()


def is_ui_friendly_sentence(text: str, *, min_len: int = 14) -> bool:
    if len(text) < min_len:
        return False
    if any(p.search(text) for p in _TECHNICAL_RESIDUE_PATTERNS):
        return False
    cyr = len(re.findall(r"[А-Яа-яЁё]", text))
    lat = len(re.findall(r"[A-Za-z]", text))
    if cyr == 0:
        return False
    if lat > cyr:
        return False
    return True


def dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = re.sub(r"\s+", " ", item).strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def sanitize_reviewer_text(
    text: str,
    *,
    max_sentences: int = 4,
    max_sentence_chars: int = 150,
    max_total_chars: int = 400,
) -> str:
    cleaned = strip_technical_residue(text)
    candidates: list[str] = []
    for sentence in split_sentences(cleaned):
        normalized = truncate_sentence(strip_technical_residue(sentence), max_sentence_chars)
        if is_ui_friendly_sentence(normalized):
            candidates.append(normalized)
    candidates = dedupe_keep_order(candidates)
    if not candidates:
        return ""
    summary = " ".join(candidates[:max_sentences]).strip()
    return truncate_sentence(summary, max_total_chars)
