"""Review-hardened tests: video pipeline outcomes and commission mapper (no ffmpeg)."""

from __future__ import annotations

from types import SimpleNamespace

from invision_api.commission.application.personal_info_mapper import _map_video_presentation_commission
from invision_api.services.video_processing.pipeline import run_presentation_pipeline


def test_invalid_url_is_failed_status() -> None:
    o = run_presentation_pipeline("not-a-url")
    assert o.media_status == "failed"
    assert o.errors
    assert o.frames_extracted_success == 0


def test_map_commission_failed_only_url() -> None:
    row = SimpleNamespace(
        media_status="failed",
        duration_sec=120,
        total_frames_analyzed=6,
        likely_face_visible=True,
        summary_text="x",
    )
    v = _map_video_presentation_commission("https://example.com/v.mp4", row)
    assert v == {"url": "https://example.com/v.mp4"}


def test_map_commission_visibility_requires_min_frames() -> None:
    row = SimpleNamespace(
        media_status="ready",
        duration_sec=120,
        total_frames_analyzed=3,
        likely_face_visible=True,
        summary_text="Краткое содержание.",
    )
    v = _map_video_presentation_commission("https://example.com/v.mp4", row)
    assert v is not None
    assert v.get("duration") == "2:00"
    assert v.get("candidateVisibility") is None
    assert v.get("summary")


def test_map_commission_ready_full_visibility() -> None:
    row = SimpleNamespace(
        media_status="ready",
        duration_sec=125,
        total_frames_analyzed=6,
        likely_face_visible=False,
        summary_text="Текст не обнаружен",
    )
    v = _map_video_presentation_commission("https://example.com/v.mp4", row)
    assert v.get("candidateVisibility") == "кандидата не видно"
