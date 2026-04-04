from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_face_cascade = None


def _get_cascade():
    global _face_cascade
    if _face_cascade is not None:
        return _face_cascade
    try:
        import cv2  # noqa: PLC0415

        p = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _face_cascade = cv2.CascadeClassifier(p)
        return _face_cascade
    except Exception:
        logger.exception("opencv cascade load failed")
        return None


def frame_has_face(path: Path) -> bool:
    """Return True if at least one frontal face is detected (heuristic)."""
    cascade = _get_cascade()
    if cascade is None or cascade.empty():
        return False
    try:
        import cv2  # noqa: PLC0415

        img = cv2.imread(str(path))
        if img is None:
            return False
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(48, 48))
        return len(faces) > 0
    except Exception:
        logger.exception("face detection failed for %s", path)
        return False
