"""Юнит-тесты разбора URL и evaluate_presentation_video без внешней сети."""

from __future__ import annotations

import pytest

from invision_api.services.link_validation.classifier import classify_url
from invision_api.services.link_validation.config import LinkValidationConfig
from invision_api.services.link_validation.presentation_video import (
    evaluate_presentation_video,
    extract_google_drive_file_id,
    parse_youtube_video_id,
)
from invision_api.services.link_validation.types import ClassificationResult, HttpProbeResult


def test_parse_youtube_watch() -> None:
    vid, bad = parse_youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert vid == "dQw4w9WgXcQ"
    assert bad is None


def test_parse_youtube_shorts() -> None:
    vid, bad = parse_youtube_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ")
    assert vid == "dQw4w9WgXcQ"
    assert bad is None


def test_parse_youtube_youtu_be() -> None:
    vid, bad = parse_youtube_video_id("https://youtu.be/dQw4w9WgXcQ")
    assert vid == "dQw4w9WgXcQ"
    assert bad is None


def test_parse_youtube_playlist_rejected() -> None:
    vid, bad = parse_youtube_video_id("https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4UEP")
    assert vid is None
    assert bad == "playlist"


def test_parse_youtube_channel_rejected() -> None:
    vid, bad = parse_youtube_video_id("https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxxx")
    assert vid is None
    assert bad == "channel_page"


def test_parse_youtube_handle_rejected() -> None:
    vid, bad = parse_youtube_video_id("https://www.youtube.com/@SomeChannel")
    assert vid is None
    assert bad == "channel_page"


def test_extract_drive_file_id() -> None:
    assert extract_google_drive_file_id("https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/view") == "1AbCdEfGhIjKlMnOpQrStUvWxYz"
    assert extract_google_drive_file_id("https://drive.google.com/uc?export=download&id=ABC123xyz") == "ABC123xyz"


def _probe_video_mp4() -> HttpProbeResult:
    return HttpProbeResult(
        final_url="https://cdn.example.com/a.mp4",
        status_code=200,
        content_type="video/mp4",
        content_length=1000,
        redirected=False,
        redirect_count=0,
        response_time_ms=10,
        body_snippet=None,
    )


def test_evaluate_direct_video_mime() -> None:
    cfg = LinkValidationConfig()
    url = "https://files.example.com/pres.mp4"
    cl = classify_url(url, "video/mp4", cfg)
    r = evaluate_presentation_video(
        original_url=url,
        normalized_url=url,
        probe=_probe_video_mp4(),
        classification=cl,
        is_reachable=True,
        availability_errors=[],
        config=cfg,
        probe_client=None,
    )
    assert r.provider == "direct"
    assert r.isProcessableVideo is True
    assert r.isValid is True


def test_evaluate_direct_pdf_rejected() -> None:
    cfg = LinkValidationConfig()
    url = "https://files.example.com/x.pdf"
    probe = HttpProbeResult(
        final_url=url,
        status_code=200,
        content_type="application/pdf",
        content_length=100,
        redirected=False,
        redirect_count=0,
        response_time_ms=10,
        body_snippet=None,
    )
    cl = classify_url(url, "application/pdf", cfg)
    r = evaluate_presentation_video(
        original_url=url,
        normalized_url=url,
        probe=probe,
        classification=cl,
        is_reachable=True,
        availability_errors=[],
        config=cfg,
        probe_client=None,
    )
    assert r.isProcessableVideo is False
    assert r.isValid is False


def test_evaluate_youtube_ok_without_probe_body() -> None:
    cfg = LinkValidationConfig()
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    probe = HttpProbeResult(
        final_url=url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        content_length=None,
        redirected=False,
        redirect_count=0,
        response_time_ms=10,
        body_snippet=None,
    )
    cl = classify_url(url, probe.content_type, cfg)
    r = evaluate_presentation_video(
        original_url=url,
        normalized_url=url,
        probe=probe,
        classification=cl,
        is_reachable=True,
        availability_errors=[],
        config=cfg,
        probe_client=None,
    )
    assert r.provider == "youtube"
    assert r.resourceType == "video"
    assert r.isProcessableVideo is True
    assert r.isValid is True


def test_evaluate_drive_folder_rejected() -> None:
    cfg = LinkValidationConfig()
    url = "https://drive.google.com/drive/folders/1abcDEFghijklmnop"
    probe = HttpProbeResult(
        final_url=url,
        status_code=200,
        content_type="text/html",
        content_length=None,
        redirected=False,
        redirect_count=0,
        response_time_ms=10,
        body_snippet="<html></html>",
    )
    cl = classify_url(url, probe.content_type, cfg)
    r = evaluate_presentation_video(
        original_url=url,
        normalized_url=url,
        probe=probe,
        classification=cl,
        is_reachable=True,
        availability_errors=[],
        config=cfg,
        probe_client=None,
    )
    assert r.provider == "google_drive"
    assert r.resourceType == "folder"
    assert r.isProcessableVideo is False


def test_evaluate_dropbox_public_video_by_extension() -> None:
    cfg = LinkValidationConfig()
    url = "https://www.dropbox.com/scl/fi/abc123/presentation.mp4?rlkey=xyz&dl=0"
    probe = HttpProbeResult(
        final_url=url,
        status_code=200,
        content_type="text/html",
        content_length=None,
        redirected=False,
        redirect_count=0,
        response_time_ms=14,
        body_snippet="<html>Dropbox</html>",
    )
    cl = classify_url(url, probe.content_type, cfg)
    r = evaluate_presentation_video(
        original_url=url,
        normalized_url=url,
        probe=probe,
        classification=cl,
        is_reachable=True,
        availability_errors=[],
        config=cfg,
        probe_client=None,
    )
    assert r.provider == "dropbox"
    assert r.resourceType == "video"
    assert r.isProcessableVideo is True
    assert r.isValid is True


def test_evaluate_dropbox_folder_rejected() -> None:
    cfg = LinkValidationConfig()
    url = "https://www.dropbox.com/sh/abc123/shared-folder?dl=0"
    probe = HttpProbeResult(
        final_url=url,
        status_code=200,
        content_type="text/html",
        content_length=None,
        redirected=False,
        redirect_count=0,
        response_time_ms=10,
        body_snippet="<html>Dropbox folder</html>",
    )
    cl = classify_url(url, probe.content_type, cfg)
    r = evaluate_presentation_video(
        original_url=url,
        normalized_url=url,
        probe=probe,
        classification=cl,
        is_reachable=True,
        availability_errors=[],
        config=cfg,
        probe_client=None,
    )
    assert r.provider == "dropbox"
    assert r.resourceType == "folder"
    assert r.isProcessableVideo is False
    assert r.isValid is False


def test_evaluate_google_docs_rejected() -> None:
    cfg = LinkValidationConfig()
    url = "https://docs.google.com/document/d/abc123/edit"
    probe = HttpProbeResult(
        final_url=url,
        status_code=200,
        content_type="text/html",
        content_length=None,
        redirected=False,
        redirect_count=0,
        response_time_ms=10,
        body_snippet=None,
    )
    cl = ClassificationResult(provider="google_docs", resource_type="cloud_resource")
    r = evaluate_presentation_video(
        original_url=url,
        normalized_url=url,
        probe=probe,
        classification=cl,
        is_reachable=True,
        availability_errors=[],
        config=cfg,
        probe_client=None,
    )
    assert r.isProcessableVideo is False
    assert r.isValid is False


@pytest.mark.parametrize(
    ("ext", "mime"),
    [
        (".mp4", None),
        (".webm", "application/octet-stream"),
    ],
)
def test_evaluate_direct_by_extension(ext: str, mime: str | None) -> None:
    cfg = LinkValidationConfig()
    url = f"https://x.example.com/a{ext}"
    ct = mime or "application/octet-stream"
    probe = HttpProbeResult(
        final_url=url,
        status_code=200,
        content_type=ct,
        content_length=100,
        redirected=False,
        redirect_count=0,
        response_time_ms=10,
        body_snippet=None,
    )
    cl = classify_url(url, ct, cfg)
    r = evaluate_presentation_video(
        original_url=url,
        normalized_url=url,
        probe=probe,
        classification=cl,
        is_reachable=True,
        availability_errors=[],
        config=cfg,
        probe_client=None,
    )
    assert r.isProcessableVideo is True, (ext, r.errors)
