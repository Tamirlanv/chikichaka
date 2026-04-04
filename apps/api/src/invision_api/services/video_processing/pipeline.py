from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from invision_api.services.video_processing import ffmpeg_tools
from invision_api.services.video_processing.constants import (
    COMMISSION_NO_TEXT,
    FACE_VISIBLE_MIN_FRAMES,
    MAX_AUDIO_FOR_TRANSCRIPTION_SEC,
    MAX_INPUT_DURATION_SEC,
    MEDIA_STATUS_FAILED,
    MEDIA_STATUS_PARTIAL,
    MEDIA_STATUS_READY,
    MIN_FRAMES_FOR_VISIBILITY_UI,
    MIN_TRANSCRIPT_CHARS,
    SAMPLE_FRAME_COUNT,
)
from invision_api.services.video_processing.face_detection_opencv import frame_has_face
from invision_api.services.video_processing.summary_openai import summarize_transcript_ru
from invision_api.services.video_processing.transcription_openai import transcribe_audio_wav

logger = logging.getLogger(__name__)


@dataclass
class VideoPipelineOutcome:
    duration_sec: int | None
    duration_formatted: str | None
    width: int | None
    height: int | None
    has_video_track: bool
    has_audio_track: bool
    sampled_timestamps_sec: list[float]
    frames_extracted_success: int
    face_detected_frames_count: int
    raw_transcript: str
    transcript_confidence: float | None
    commission_summary: str
    candidate_visible: bool
    has_speech: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    media_status: str = MEDIA_STATUS_READY


def _format_duration(total_sec: float) -> str:
    sec = int(round(total_sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _failed_outcome(*, errors: list[str], warnings: list[str] | None = None) -> VideoPipelineOutcome:
    w = warnings or []
    return VideoPipelineOutcome(
        duration_sec=None,
        duration_formatted=None,
        width=None,
        height=None,
        has_video_track=False,
        has_audio_track=False,
        sampled_timestamps_sec=[],
        frames_extracted_success=0,
        face_detected_frames_count=0,
        raw_transcript="",
        transcript_confidence=None,
        commission_summary=COMMISSION_NO_TEXT,
        candidate_visible=False,
        has_speech=False,
        warnings=w,
        errors=errors,
        media_status=MEDIA_STATUS_FAILED,
    )


def run_presentation_pipeline(video_url: str) -> VideoPipelineOutcome:
    """Download/process video locally and produce signals for commission + internal storage."""
    warnings: list[str] = []
    errors: list[str] = []
    url = (video_url or "").strip()
    if not url.startswith(("http://", "https://")):
        return _failed_outcome(errors=["Некорректный URL видео"])

    tmpdir = tempfile.mkdtemp(prefix="vpipe_")
    local_video: Path | None = None
    try:
        local_video = ffmpeg_tools.make_temp_video_path()
        try:
            ffmpeg_tools.download_or_copy_url_to_file(url, local_video, max_seconds=MAX_INPUT_DURATION_SEC)
        except ffmpeg_tools.FFmpegError as exc:
            logger.warning("ffmpeg download failed: %s", exc)
            return _failed_outcome(
                errors=["Не удалось загрузить видео по ссылке. Проверьте доступность и формат."],
            )

        if not ffmpeg_tools.has_video_stream(local_video):
            return _failed_outcome(errors=["По ссылке не обнаружена видеодорожка."])

        duration = ffmpeg_tools.probe_duration_sec(local_video)
        if duration <= 0:
            return _failed_outcome(errors=["Не удалось определить длительность видео или файл повреждён."])

        dur_int = int(round(duration))
        w, h = ffmpeg_tools.video_dimensions(local_video)
        has_v = True
        has_a = ffmpeg_tools.has_audio_stream(local_video)

        times: list[float] = []
        for i in range(SAMPLE_FRAME_COUNT):
            times.append((i + 0.5) * duration / SAMPLE_FRAME_COUNT)

        face_hits = 0
        frames_ok = 0
        for i, t in enumerate(times):
            png = Path(tmpdir) / f"f{i}.png"
            try:
                ffmpeg_tools.extract_frame_png(local_video, png, timestamp_sec=t)
                frames_ok += 1
                if frame_has_face(png):
                    face_hits += 1
            except ffmpeg_tools.FFmpegError:
                warnings.append(f"Не удалось извлечь кадр #{i + 1}.")

        candidate_visible = False
        if frames_ok >= MIN_FRAMES_FOR_VISIBILITY_UI:
            candidate_visible = face_hits >= FACE_VISIBLE_MIN_FRAMES
        elif frames_ok > 0:
            candidate_visible = face_hits >= FACE_VISIBLE_MIN_FRAMES
        else:
            errors.append("Не удалось извлечь кадры для проверки лица.")

        if 0 < frames_ok < MIN_FRAMES_FOR_VISIBILITY_UI:
            errors.append("Недостаточно кадров для устойчивой проверки лица (частичный сбой извлечения).")

        raw = ""
        tr_conf: float | None = None
        if has_a:
            wav = Path(tmpdir) / "audio.wav"
            try:
                audio_cap = min(MAX_AUDIO_FOR_TRANSCRIPTION_SEC, duration)
                ffmpeg_tools.extract_audio_wav_16k_mono(local_video, wav, max_seconds=audio_cap)
                raw, tr_conf = transcribe_audio_wav(wav)
            except ffmpeg_tools.FFmpegError:
                warnings.append("Не удалось извлечь аудио для транскрибации.")
        else:
            warnings.append("Аудиодорожка не обнаружена.")

        has_speech = len(raw.strip()) >= MIN_TRANSCRIPT_CHARS
        if has_speech:
            try:
                summary = summarize_transcript_ru(raw).strip()
            except Exception:
                logger.exception("summary layer raised")
                summary = ""
            if not summary:
                summary = COMMISSION_NO_TEXT
        else:
            summary = COMMISSION_NO_TEXT

        if errors:
            media = MEDIA_STATUS_PARTIAL if frames_ok > 0 or has_v else MEDIA_STATUS_FAILED
        else:
            media = MEDIA_STATUS_READY

        return VideoPipelineOutcome(
            duration_sec=dur_int,
            duration_formatted=_format_duration(duration),
            width=w,
            height=h,
            has_video_track=has_v,
            has_audio_track=has_a,
            sampled_timestamps_sec=times,
            frames_extracted_success=frames_ok,
            face_detected_frames_count=face_hits,
            raw_transcript=raw,
            transcript_confidence=tr_conf,
            commission_summary=summary,
            candidate_visible=candidate_visible,
            has_speech=has_speech,
            warnings=warnings,
            errors=errors,
            media_status=media,
        )
    finally:
        try:
            if local_video and local_video.exists():
                local_video.unlink(missing_ok=True)
        except OSError:
            pass
        shutil.rmtree(tmpdir, ignore_errors=True)
