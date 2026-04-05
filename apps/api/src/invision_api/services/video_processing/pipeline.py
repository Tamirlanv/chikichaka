from __future__ import annotations

import logging
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from invision_api.services.video_processing import ffmpeg_tools
from invision_api.services.link_validation.service import validate_presentation_video_only
from invision_api.services.video_processing.constants import (
    COMMISSION_NO_TEXT,
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
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

_INGESTION_YOUTUBE = "youtube_ytdlp"
_INGESTION_GOOGLE_DRIVE = "google_drive_direct_download"
_INGESTION_DROPBOX = "dropbox_direct_download"
_INGESTION_DIRECT = "direct_ffmpeg"
_INGESTION_NONE = "none"


@dataclass
class VideoPipelineOutcome:
    provider: str
    resource_type: str
    ingestion_strategy: str
    normalized_url: str | None
    access_status: str
    duration_sec: int | None
    duration_formatted: str | None
    width: int | None
    height: int | None
    codec_video: str | None
    codec_audio: str | None
    container: str | None
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
        provider="unknown",
        resource_type="unknown",
        ingestion_strategy=_INGESTION_NONE,
        normalized_url=None,
        access_status="invalid",
        duration_sec=None,
        duration_formatted=None,
        width=None,
        height=None,
        codec_video=None,
        codec_audio=None,
        container=None,
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


def _failed_outcome_with_context(
    *,
    errors: list[str],
    warnings: list[str],
    provider: str,
    resource_type: str,
    ingestion_strategy: str,
    normalized_url: str | None,
    access_status: str,
) -> VideoPipelineOutcome:
    out = _failed_outcome(errors=errors, warnings=warnings)
    out.provider = provider or "unknown"
    out.resource_type = resource_type or "unknown"
    out.ingestion_strategy = ingestion_strategy
    out.normalized_url = normalized_url
    out.access_status = access_status
    return out


def _cap_summary_sentences(text: str, *, max_sentences: int = 6) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(s) if p.strip()]
    if not parts or len(parts) <= max_sentences:
        return s
    return " ".join(parts[:max_sentences]).strip()


def _normalized_exception_message(exc: Exception, *, fallback: str) -> str:
    msg = str(exc).strip()
    return msg or fallback


def _ingestion_error_message(exc: Exception) -> str:
    reason = _normalized_exception_message(
        exc,
        fallback="Не удалось загрузить видео по ссылке. Проверьте доступность и формат.",
    )
    return f"Не удалось загрузить видео: {reason}"


def _resolve_ingestion_source(*, provider: str, normalized_url: str) -> tuple[str, str]:
    if provider == "youtube":
        return normalized_url, _INGESTION_YOUTUBE
    if provider == "google_drive":
        direct = ffmpeg_tools.normalize_google_drive_download_url(normalized_url)
        if not direct:
            raise ffmpeg_tools.FFmpegError("Не удалось определить файл Google Drive для загрузки.")
        return direct, _INGESTION_GOOGLE_DRIVE
    if provider == "dropbox":
        direct = ffmpeg_tools.normalize_dropbox_download_url(normalized_url)
        if not direct:
            raise ffmpeg_tools.FFmpegError("Ссылка Dropbox указывает на папку или недоступный ресурс.")
        return direct, _INGESTION_DROPBOX
    return normalized_url, _INGESTION_DIRECT


def run_presentation_pipeline(video_url: str) -> VideoPipelineOutcome:
    """Download/process video locally and produce signals for commission + internal storage."""
    url = (video_url or "").strip()
    if not url.startswith(("http://", "https://")):
        return _failed_outcome(errors=["Некорректный URL видео"])

    preflight = validate_presentation_video_only(url)
    normalized_url = (preflight.normalizedUrl or url).strip()
    provider = preflight.provider
    resource_type = preflight.resourceType
    warnings: list[str] = list(preflight.warnings or [])
    errors: list[str] = []
    access_status = "reachable" if preflight.isAccessible else "unreachable"

    if not preflight.isProcessableVideo:
        reason = (preflight.errors[0] if preflight.errors else None) or "Ссылка не указывает на видеофайл."
        return _failed_outcome_with_context(
            errors=[reason],
            warnings=warnings,
            provider=provider,
            resource_type=resource_type,
            ingestion_strategy=_INGESTION_NONE,
            normalized_url=normalized_url,
            access_status=access_status,
        )
    if not preflight.isValid:
        reason = (preflight.errors[0] if preflight.errors else None) or "Видео по ссылке недоступно для обработки."
        return _failed_outcome_with_context(
            errors=[reason],
            warnings=warnings,
            provider=provider,
            resource_type=resource_type,
            ingestion_strategy=_INGESTION_NONE,
            normalized_url=normalized_url,
            access_status=access_status,
        )

    try:
        ingestion_url, ingestion_strategy = _resolve_ingestion_source(provider=provider, normalized_url=normalized_url)
    except ffmpeg_tools.FFmpegError as exc:
        return _failed_outcome_with_context(
            errors=[str(exc)],
            warnings=warnings,
            provider=provider,
            resource_type=resource_type,
            ingestion_strategy=_INGESTION_NONE,
            normalized_url=normalized_url,
            access_status=access_status,
        )

    tmpdir = tempfile.mkdtemp(prefix="vpipe_")
    local_video: Path | None = None
    try:
        local_video = ffmpeg_tools.make_temp_video_path()
        try:
            try:
                ffmpeg_tools.download_media_url_to_file(ingestion_url, local_video, max_seconds=MAX_INPUT_DURATION_SEC)
            except ffmpeg_tools.FFmpegError as exc:
                logger.warning("ffmpeg download failed: %s", exc)
                return _failed_outcome_with_context(
                    errors=[_ingestion_error_message(exc)],
                    warnings=warnings,
                    provider=provider,
                    resource_type=resource_type,
                    ingestion_strategy=ingestion_strategy,
                    normalized_url=normalized_url,
                    access_status=access_status,
                )

            try:
                metadata = ffmpeg_tools.probe_media_metadata(local_video)
            except ffmpeg_tools.FFmpegError as exc:
                return _failed_outcome_with_context(
                    errors=[f"Не удалось прочитать метаданные видео: {_normalized_exception_message(exc, fallback='ffprobe error')}"],
                    warnings=warnings,
                    provider=provider,
                    resource_type=resource_type,
                    ingestion_strategy=ingestion_strategy,
                    normalized_url=normalized_url,
                    access_status=access_status,
                )
            if not metadata.has_video:
                return _failed_outcome_with_context(
                    errors=["По ссылке не обнаружена видеодорожка."],
                    warnings=warnings,
                    provider=provider,
                    resource_type=resource_type,
                    ingestion_strategy=ingestion_strategy,
                    normalized_url=normalized_url,
                    access_status=access_status,
                )

            duration = metadata.duration_sec
            if duration <= 0:
                return _failed_outcome_with_context(
                    errors=["Не удалось определить длительность видео или файл повреждён."],
                    warnings=warnings,
                    provider=provider,
                    resource_type=resource_type,
                    ingestion_strategy=ingestion_strategy,
                    normalized_url=normalized_url,
                    access_status=access_status,
                )

            dur_int = int(round(duration))
            w, h = metadata.width, metadata.height
            has_v = metadata.has_video
            has_a = metadata.has_audio

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
                except Exception:
                    warnings.append(f"Не удалось проанализировать кадр #{i + 1}.")
                    logger.exception("frame analysis failed frame=%s", i + 1)

            if frames_ok <= 0:
                errors.append("Не удалось извлечь кадры для проверки лица.")
            candidate_visible = frames_ok > 0 and face_hits >= 1

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
                except Exception:
                    warnings.append("Не удалось распознать речь из аудио.")
                    logger.exception("transcription layer raised")
            else:
                warnings.append("Аудиодорожка не обнаружена.")

            has_speech = len(raw.strip()) >= MIN_TRANSCRIPT_CHARS
            if has_speech:
                try:
                    summary = summarize_transcript_ru(raw).strip()
                except Exception:
                    logger.exception("summary layer raised")
                    summary = ""
                summary = _cap_summary_sentences(summary)
                if not summary:
                    summary = COMMISSION_NO_TEXT
            else:
                summary = COMMISSION_NO_TEXT

            if errors:
                media = MEDIA_STATUS_PARTIAL if frames_ok > 0 or has_v else MEDIA_STATUS_FAILED
            else:
                media = MEDIA_STATUS_READY

            return VideoPipelineOutcome(
                provider=provider,
                resource_type=resource_type,
                ingestion_strategy=ingestion_strategy,
                normalized_url=normalized_url,
                access_status=access_status,
                duration_sec=dur_int,
                duration_formatted=_format_duration(duration),
                width=w,
                height=h,
                codec_video=metadata.codec_video,
                codec_audio=metadata.codec_audio,
                container=metadata.container,
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
        except Exception as exc:
            logger.exception("video pipeline crashed")
            return _failed_outcome_with_context(
                errors=[f"Внутренняя ошибка видео-пайплайна: {_normalized_exception_message(exc, fallback='unknown error')}"],
                warnings=warnings,
                provider=provider,
                resource_type=resource_type,
                ingestion_strategy=ingestion_strategy,
                normalized_url=normalized_url,
                access_status=access_status,
            )
    finally:
        try:
            if local_video and local_video.exists():
                local_video.unlink(missing_ok=True)
        except OSError:
            pass
        shutil.rmtree(tmpdir, ignore_errors=True)
