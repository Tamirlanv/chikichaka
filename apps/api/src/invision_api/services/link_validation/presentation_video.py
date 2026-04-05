from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from invision_api.services.link_validation.config import LinkValidationConfig
from invision_api.services.link_validation.http_client import HttpProbeClient
from invision_api.services.link_validation.types import (
    ClassificationResult,
    HttpProbeResult,
    VideoLinkValidationResult,
    VideoPresentationProvider,
    VideoPresentationResourceType,
)

_YT_ID = re.compile(r"^[a-zA-Z0-9_-]{11}$")
_FILE_D = re.compile(r"/file/d/([a-zA-Z0-9_-]+)")
_GOOGLE_APPS_NON_VIDEO = (
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
    "application/vnd.google-apps.form",
    "application/vnd.google-apps.drawing",
    "application/vnd.google-apps.map",
    "application/vnd.google-apps.fusiontable",
)

MSG_DRIVE_FOLDER = "Указана ссылка на папку Google Drive. Укажите прямую ссылку на видеофайл."
MSG_DRIVE_NOT_FILE = "Ссылка Google Drive не указывает на файл (ожидается /file/d/… или прямая загрузка)."
MSG_DRIVE_NOT_VIDEO = "Файл в Google Drive не похож на видео (документ или другой тип)."
MSG_DOCS_NOT_VIDEO = "Ссылка ведёт на Google Документы/Таблицы/Презентации, а не на видео."
MSG_YT_NOT_VIDEO_PAGE = "Ссылка YouTube должна вести на конкретное видео (watch, Shorts, embed), а не на канал или плейлист."
MSG_DIRECT_NOT_VIDEO = (
    "По ссылке не обнаружен видеофайл. Укажите прямую ссылку на видео (video/*) или YouTube / Google Drive / Dropbox."
)
MSG_DROPBOX_FOLDER = "Указана ссылка на папку Dropbox. Укажите публичную ссылку на файл с видео."
MSG_DROPBOX_NOT_VIDEO = "Ссылка Dropbox не указывает на видеофайл."
MSG_UNSUPPORTED_HOST = (
    "Для презентации поддерживаются YouTube, Google Drive/Dropbox (публичный файл с видео) "
    "или прямая ссылка на видеофайл."
)
WARN_DRIVE_UNCERTAIN_VIDEO = (
    "Не удалось однозначно подтвердить, что в Google Drive лежит видео. Убедитесь, что по ссылке открывается именно видео."
)


def _lower_path(url: str) -> str:
    return urlsplit(url).path.lower()


def _path_ext(url: str) -> str | None:
    path = urlsplit(url).path
    if "." not in path:
        return None
    return path[path.rfind(".") :].lower()


def _is_youtube_host(host: str) -> bool:
    h = host.lower()
    return h in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"} or h.endswith(
        ".youtube.com"
    )


def _is_dropbox_folder_url(url: str) -> bool:
    path = _lower_path(url)
    return "/sh/" in path or "/scl/fo/" in path


def _dropbox_url_suggests_video(url: str, *, config: LinkValidationConfig) -> bool:
    ext = _path_ext(url)
    return bool(ext and ext in config.presentation_video_extensions)


def parse_youtube_video_id(url: str) -> tuple[str | None, VideoPresentationResourceType | None]:
    """Returns (video_id or None, rejection_reason resource type if URL is clearly not a single video)."""
    sp = urlsplit(url)
    host = (sp.hostname or "").lower()
    if not _is_youtube_host(host):
        return None, None

    path = sp.path or ""
    pl = path.lower()
    qs = parse_qs(sp.query)

    if "youtu.be" in host:
        seg = [s for s in path.split("/") if s]
        if not seg:
            return None, "channel_page"
        vid = seg[0].split("?")[0]
        if _YT_ID.match(vid):
            return vid, None
        return None, "unsupported_page"

    if "/playlist" in pl or (qs.get("list") and not qs.get("v")):
        return None, "playlist"
    if re.match(r"^/channel/[^/]+/?$", path) and not qs.get("v"):
        return None, "channel_page"
    if pl.startswith("/feed") or pl == "/" or pl == "":
        if not qs.get("v"):
            return None, "channel_page"
    if re.match(r"^/@[^/]+/?$", path) or re.match(r"^/@[^/]+/featured/?$", path):
        return None, "channel_page"
    if "/channel/" in pl and "/channel/uc" in pl.replace(" ", "").lower():
        if not qs.get("v") and "/watch" not in pl:
            return None, "channel_page"
    if re.match(r"^/c/[^/]+/?$", path) or re.match(r"^/user/[^/]+/?$", path):
        if not qs.get("v"):
            return None, "channel_page"

    vids = qs.get("v", [])
    if vids:
        for v in vids:
            if _YT_ID.match(v):
                return v, None
        return None, "unsupported_page"

    m = re.match(r"^/(?:embed|shorts|live|v)/([a-zA-Z0-9_-]{11})/?", path)
    if m and _YT_ID.match(m.group(1)):
        return m.group(1), None

    return None, "unsupported_page"


def extract_google_drive_file_id(url: str) -> str | None:
    sp = urlsplit(url)
    path = sp.path or ""
    qs = parse_qs(sp.query)
    m = _FILE_D.search(path)
    if m:
        return m.group(1)
    ids = qs.get("id", [])
    if ids:
        return ids[0]
    return None


def _snippet_suggests_google_apps_non_video(snippet: str | None) -> bool:
    if not snippet:
        return False
    s = snippet.lower()
    return any(x in s for x in _GOOGLE_APPS_NON_VIDEO)


def _snippet_suggests_video(snippet: str | None) -> bool:
    if not snippet:
        return False
    s = snippet.lower()
    if "mimetype" in s and "video/" in s:
        return True
    if 'og:type" content="video' in s or "og:type' content='video" in s:
        return True
    if "youtube.com/embed/" in s:
        return True
    return False


def _mime_is_video(mime: str | None) -> bool:
    if not mime:
        return False
    m = mime.lower().split(";")[0].strip()
    return m.startswith("video/")


def evaluate_presentation_video(
    *,
    original_url: str,
    normalized_url: str,
    probe: HttpProbeResult,
    classification: ClassificationResult,
    is_reachable: bool,
    availability_errors: list[str],
    config: LinkValidationConfig,
    probe_client: HttpProbeClient | None = None,
) -> VideoLinkValidationResult:
    """Оценивает пригодность ссылки для видео-презентации без повторного HTTP GET страницы."""
    client = probe_client
    warnings: list[str] = []
    errors: list[str] = []
    ct = (probe.content_type or "").split(";")[0].strip() if probe.content_type else None
    final_u = probe.final_url or normalized_url
    sp = urlsplit(normalized_url)
    host = (sp.hostname or "").lower()

    provider: VideoPresentationProvider = "unknown"
    resource_type: VideoPresentationResourceType = "unknown"
    is_processable = False
    detected_mime = ct
    detected_ext = _path_ext(final_u) or _path_ext(normalized_url)

    # --- Google Docs (not video) ---
    if host == "docs.google.com" or classification.provider == "google_docs":
        provider = "google_drive"
        resource_type = "document"
        errors.append(MSG_DOCS_NOT_VIDEO)
        return VideoLinkValidationResult(
            isValid=False,
            provider=provider,
            resourceType=resource_type,
            isAccessible=is_reachable,
            isProcessableVideo=False,
            detectedMimeType=detected_mime,
            detectedExtension=detected_ext,
            errors=errors,
            warnings=warnings,
        )

    # --- YouTube ---
    if classification.provider == "youtube" or _is_youtube_host(host):
        provider = "youtube"
        vid, bad_res = parse_youtube_video_id(final_u)
        if not vid:
            vid2, bad_res2 = parse_youtube_video_id(normalized_url)
            vid, bad_res = vid2, bad_res2
        if vid and _YT_ID.match(vid):
            resource_type = "video"
            is_processable = True
            merged = list(dict.fromkeys(errors + (availability_errors or [])))
            return VideoLinkValidationResult(
                isValid=is_reachable and is_processable and not merged,
                provider=provider,
                resourceType=resource_type,
                isAccessible=is_reachable,
                isProcessableVideo=is_processable,
                detectedMimeType=detected_mime,
                detectedExtension=detected_ext,
                errors=merged,
                warnings=warnings,
            )
        resource_type = bad_res or "unsupported_page"
        errors.append(MSG_YT_NOT_VIDEO_PAGE)
        return VideoLinkValidationResult(
            isValid=False,
            provider=provider,
            resourceType=resource_type,
            isAccessible=is_reachable,
            isProcessableVideo=False,
            detectedMimeType=detected_mime,
            detectedExtension=detected_ext,
            errors=errors,
            warnings=warnings,
        )

    # --- Google Drive ---
    if host == "drive.google.com" or classification.provider == "google_drive":
        provider = "google_drive"
        pl = _lower_path(normalized_url)
        if "/drive/folders/" in pl:
            resource_type = "folder"
            errors.append(MSG_DRIVE_FOLDER)
            return VideoLinkValidationResult(
                isValid=False,
                provider=provider,
                resourceType=resource_type,
                isAccessible=is_reachable,
                isProcessableVideo=False,
                detectedMimeType=detected_mime,
                detectedExtension=detected_ext,
                errors=errors,
                warnings=warnings,
            )

        file_id = extract_google_drive_file_id(normalized_url)

        if not file_id:
            resource_type = "unsupported_page"
            errors.append(MSG_DRIVE_NOT_FILE)
            return VideoLinkValidationResult(
                isValid=False,
                provider=provider,
                resourceType=resource_type,
                isAccessible=is_reachable,
                isProcessableVideo=False,
                detectedMimeType=detected_mime,
                detectedExtension=detected_ext,
                errors=errors,
                warnings=warnings,
            )

        snippet = probe.body_snippet
        if _snippet_suggests_google_apps_non_video(snippet):
            resource_type = "document"
            errors.append(MSG_DRIVE_NOT_VIDEO)
            return VideoLinkValidationResult(
                isValid=False,
                provider=provider,
                resourceType=resource_type,
                isAccessible=is_reachable,
                isProcessableVideo=False,
                detectedMimeType=detected_mime,
                detectedExtension=detected_ext,
                errors=errors,
                warnings=warnings,
            )

        if _mime_is_video(ct):
            resource_type = "video"
            is_processable = True
        elif _snippet_suggests_video(snippet):
            resource_type = "video"
            is_processable = True
        elif ct and "text/html" in ct.lower() and client:
            uc = f"https://drive.google.com/uc?export=download&id={file_id}"
            head = client.head(uc)
            hct = (head.content_type or "").split(";")[0].strip() if head.content_type else None
            detected_mime = hct or detected_mime
            hct_lower = (head.content_type or "").lower()
            if _mime_is_video(head.content_type):
                resource_type = "video"
                is_processable = True
            elif head.status_code and 200 <= head.status_code < 400:
                if "text/html" in hct_lower:
                    warnings.append(WARN_DRIVE_UNCERTAIN_VIDEO)
                    resource_type = "unknown"
                elif "octet-stream" in hct_lower:
                    resource_type = "video"
                    is_processable = True
                    warnings.append(WARN_DRIVE_UNCERTAIN_VIDEO)
                else:
                    resource_type = "file_non_video"
                    errors.append(MSG_DRIVE_NOT_VIDEO)
            else:
                warnings.append(WARN_DRIVE_UNCERTAIN_VIDEO)
                resource_type = "unknown"
        elif ct and "text/html" in ct.lower():
            warnings.append(WARN_DRIVE_UNCERTAIN_VIDEO)
            resource_type = "unknown"
        else:
            resource_type = "file_non_video"
            errors.append(MSG_DRIVE_NOT_VIDEO)

        block_errs = list(errors)
        if is_processable:
            block_errs.extend(availability_errors or [])
        if is_processable:
            resource_type = "video"
        return VideoLinkValidationResult(
            isValid=is_processable and is_reachable and not block_errs,
            provider=provider,
            resourceType=resource_type,
            isAccessible=is_reachable,
            isProcessableVideo=is_processable,
            detectedMimeType=detected_mime,
            detectedExtension=detected_ext,
            errors=list(dict.fromkeys(block_errs)),
            warnings=warnings,
        )

    # --- Dropbox ---
    if classification.provider == "dropbox":
        provider = "dropbox"
        if _is_dropbox_folder_url(final_u) or _is_dropbox_folder_url(normalized_url):
            errors.append(MSG_DROPBOX_FOLDER)
            return VideoLinkValidationResult(
                isValid=False,
                provider=provider,
                resourceType="folder",
                isAccessible=is_reachable,
                isProcessableVideo=False,
                detectedMimeType=detected_mime,
                detectedExtension=detected_ext,
                errors=errors,
                warnings=warnings,
            )
        if _mime_is_video(ct) or _dropbox_url_suggests_video(final_u, config=config) or _dropbox_url_suggests_video(
            normalized_url, config=config
        ):
            is_processable = True
            block_errs = list(dict.fromkeys(availability_errors or []))
            return VideoLinkValidationResult(
                isValid=is_processable and is_reachable and not block_errs,
                provider=provider,
                resourceType="video",
                isAccessible=is_reachable,
                isProcessableVideo=is_processable,
                detectedMimeType=detected_mime,
                detectedExtension=detected_ext,
                errors=block_errs,
                warnings=warnings,
            )
        errors.append(MSG_DROPBOX_NOT_VIDEO)
        return VideoLinkValidationResult(
            isValid=False,
            provider=provider,
            resourceType="file_non_video" if detected_ext else "web_page",
            isAccessible=is_reachable,
            isProcessableVideo=False,
            detectedMimeType=detected_mime,
            detectedExtension=detected_ext,
            errors=errors,
            warnings=warnings,
        )

    # --- Vimeo / OneDrive / unsupported clouds ---
    if classification.provider in {"vimeo", "onedrive"}:
        errors.append(MSG_UNSUPPORTED_HOST)
        return VideoLinkValidationResult(
            isValid=False,
            provider="unknown",
            resourceType="unsupported_page",
            isAccessible=is_reachable,
            isProcessableVideo=False,
            detectedMimeType=detected_mime,
            detectedExtension=detected_ext,
            errors=errors,
            warnings=warnings,
        )

    # --- Direct / generic ---
    provider = "direct"
    if _mime_is_video(ct):
        resource_type = "video"
        is_processable = True
    elif detected_ext and detected_ext in config.presentation_video_extensions:
        if ct and "text/html" in ct.lower():
            resource_type = "web_page"
            errors.append(MSG_DIRECT_NOT_VIDEO)
        else:
            resource_type = "video"
            is_processable = True
    elif ct:
        lower = ct.lower()
        if "application/pdf" in lower or lower.startswith("image/"):
            resource_type = "file_non_video"
            errors.append(MSG_DIRECT_NOT_VIDEO)
        elif "text/html" in lower and not _mime_is_video(ct):
            resource_type = "web_page"
            errors.append(MSG_DIRECT_NOT_VIDEO)
        else:
            resource_type = "file_non_video"
            errors.append(MSG_DIRECT_NOT_VIDEO)
    else:
        resource_type = "unknown"
        errors.append(MSG_DIRECT_NOT_VIDEO)

    if is_processable:
        merge_err = list(dict.fromkeys(availability_errors or []))
    else:
        merge_err = errors
    return VideoLinkValidationResult(
        isValid=is_processable and is_reachable and not merge_err,
        provider=provider,
        resourceType=resource_type,
        isAccessible=is_reachable,
        isProcessableVideo=is_processable,
        detectedMimeType=detected_mime,
        detectedExtension=detected_ext,
        errors=merge_err if is_processable else errors,
        warnings=warnings,
    )


def video_result_for_invalid_url(original_url: str, message: str) -> VideoLinkValidationResult:
    return VideoLinkValidationResult(
        isValid=False,
        provider="unknown",
        resourceType="unknown",
        isAccessible=False,
        isProcessableVideo=False,
        errors=[message],
        warnings=[],
    )
