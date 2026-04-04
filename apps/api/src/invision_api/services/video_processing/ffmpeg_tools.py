from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FFmpegError(RuntimeError):
    pass


def _run(args: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def ffprobe_json(path: Path) -> dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    proc = _run(cmd, timeout=120)
    if proc.returncode != 0:
        raise FFmpegError(proc.stderr or f"ffprobe failed with code {proc.returncode}")
    return json.loads(proc.stdout or "{}")


def probe_duration_sec(path: Path) -> float:
    data = ffprobe_json(path)
    fmt = data.get("format") or {}
    dur = fmt.get("duration")
    if dur is None:
        return 0.0
    try:
        return float(dur)
    except (TypeError, ValueError):
        return 0.0


def has_video_stream(path: Path) -> bool:
    data = ffprobe_json(path)
    for s in data.get("streams") or []:
        if s.get("codec_type") == "video":
            return True
    return False


def has_audio_stream(path: Path) -> bool:
    data = ffprobe_json(path)
    for s in data.get("streams") or []:
        if s.get("codec_type") == "audio":
            return True
    return False


def video_dimensions(path: Path) -> tuple[int | None, int | None]:
    data = ffprobe_json(path)
    for s in data.get("streams") or []:
        if s.get("codec_type") == "video":
            w, h = s.get("width"), s.get("height")
            try:
                return (int(w) if w is not None else None, int(h) if h is not None else None)
            except (TypeError, ValueError):
                return None, None
    return None, None


def extract_audio_wav_16k_mono(path: Path, out_wav: Path, *, max_seconds: float | None) -> None:
    args = [
        "ffmpeg",
        "-y",
        "-i",
        str(path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
    ]
    if max_seconds is not None and max_seconds > 0:
        args.extend(["-t", str(max_seconds)])
    args.append(str(out_wav))
    proc = _run(args, timeout=600)
    if proc.returncode != 0:
        raise FFmpegError(proc.stderr or "ffmpeg audio extract failed")


def extract_frame_png(path: Path, out_png: Path, *, timestamp_sec: float) -> None:
    args = [
        "ffmpeg",
        "-y",
        "-ss",
        str(max(0.0, timestamp_sec)),
        "-i",
        str(path),
        "-vframes",
        "1",
        "-q:v",
        "2",
        str(out_png),
    ]
    proc = _run(args, timeout=120)
    if proc.returncode != 0:
        raise FFmpegError(proc.stderr or "ffmpeg frame extract failed")


def download_or_copy_url_to_file(url: str, out_path: Path, *, max_seconds: int) -> None:
    """Copy media from URL into a local file using ffmpeg (supports many HTTP(S) and streaming sources)."""
    args = [
        "ffmpeg",
        "-y",
        "-i",
        url,
        "-c",
        "copy",
        "-t",
        str(max_seconds),
        str(out_path),
    ]
    proc = _run(args, timeout=3600)
    if proc.returncode != 0:
        raise FFmpegError(proc.stderr or "ffmpeg download failed")


def make_temp_video_path() -> Path:
    fd, name = tempfile.mkstemp(prefix="vp_", suffix=".mkv")
    import os
    os.close(fd)
    return Path(name)
