from __future__ import annotations

import re
from urllib.parse import urlsplit

from invision_api.services.link_validation.types import ClassificationResult, HttpProbeResult

_GOOGLE_ACCESS_DENIED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"you need access", re.IGNORECASE),
    re.compile(r"request access", re.IGNORECASE),
    re.compile(r"Запросить доступ", re.IGNORECASE),
    re.compile(r"Вам нужно разрешение", re.IGNORECASE),
    re.compile(r"Нет доступа", re.IGNORECASE),
    re.compile(r"Доступ запрещён", re.IGNORECASE),
    re.compile(r'data-reason="not_eligible"', re.IGNORECASE),
    re.compile(r"ServiceLogin", re.IGNORECASE),
    re.compile(r'"reason"\s*:\s*"ACL"', re.IGNORECASE),
]

_DROPBOX_ACCESS_DENIED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"this link is not available", re.IGNORECASE),
    re.compile(r"request access", re.IGNORECASE),
    re.compile(r"permission to view", re.IGNORECASE),
]

_ONEDRIVE_ACCESS_DENIED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"need permission", re.IGNORECASE),
    re.compile(r"request access", re.IGNORECASE),
    re.compile(r"access denied", re.IGNORECASE),
]


def _body_matches_patterns(body: str | None, patterns: list[re.Pattern[str]]) -> list[str]:
    if not body:
        return []
    return [p.pattern for p in patterns if p.search(body)]


def cloud_access_hints(classification: ClassificationResult, probe: HttpProbeResult) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []

    if classification.provider not in {"google_drive", "google_docs", "dropbox", "onedrive"}:
        return warnings, errors

    if probe.status_code is None:
        warnings.append("Cloud link was not fully checked due to network issue")
        return warnings, errors

    status = probe.status_code
    final_url = probe.final_url or ""
    final_path = urlsplit(final_url).path.lower()
    lower_ct = (probe.content_type or "").lower()
    body = probe.body_snippet

    if status in {401}:
        warnings.append("Cloud resource likely requires login")
    elif status in {403}:
        errors.append("Cloud resource access denied")
    elif status in {404, 410}:
        errors.append("Cloud resource is missing")
    elif status == 429:
        warnings.append("Cloud provider quota or rate limit exceeded")

    if classification.provider == "google_drive":
        if "/file/d/" not in final_path and "/uc" not in final_path and "/drive/folders/" not in final_path:
            warnings.append("Google Drive sharing mode is unusual or unsupported")
    if classification.provider == "google_docs":
        if not any(chunk in final_path for chunk in ("/document/d/", "/spreadsheets/d/", "/presentation/d/")):
            warnings.append("Google Docs sharing mode may be unsupported")

    if "text/html" in lower_ct and status == 200 and any(x in final_url.lower() for x in ("login", "signin", "auth")):
        warnings.append("Cloud link resolved to auth page, may require private access")

    if status == 200 and "text/html" in lower_ct and body:
        access_patterns: list[re.Pattern[str]] = []
        if classification.provider in {"google_drive", "google_docs"}:
            access_patterns = _GOOGLE_ACCESS_DENIED_PATTERNS
        elif classification.provider == "dropbox":
            access_patterns = _DROPBOX_ACCESS_DENIED_PATTERNS
        elif classification.provider == "onedrive":
            access_patterns = _ONEDRIVE_ACCESS_DENIED_PATTERNS

        matched = _body_matches_patterns(body, access_patterns)
        if matched:
            errors.append(
                "Cloud resource returned HTTP 200 but the page indicates restricted access — "
                "the link is likely not publicly shared"
            )

    return warnings, errors
