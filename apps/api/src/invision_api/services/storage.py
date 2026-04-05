import logging
import uuid
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

# Pre-monorepo-anchor uploads lived under apps/api/data/uploads when UPLOAD_ROOT was cwd-relative.
# Kept for read/delete so existing blobs remain reachable after UPLOAD_ROOT resolves to repo data/uploads.
_LEGACY_APPS_API_UPLOADS = Path(__file__).resolve().parents[3] / "data" / "uploads"


class StorageBackend(Protocol):
    def put(self, *, application_id: uuid.UUID, original_filename: str, data: bytes, content_type: str) -> str:
        """Persist bytes; return storage key (path relative to root or opaque id)."""

    def absolute_path(self, storage_key: str) -> Path:
        """Resolve storage key to local path for serving/admin."""

    def read_bytes(self, storage_key: str) -> bytes:
        """Load file contents."""

    def delete(self, storage_key: str) -> None: ...


class LocalStorageBackend:
    def __init__(self, root: str) -> None:
        self._root = Path(root)

    def put(self, *, application_id: uuid.UUID, original_filename: str, data: bytes, content_type: str) -> str:
        ext = Path(original_filename).suffix[:16] or ""
        safe = f"{uuid.uuid4().hex}{ext}"
        app_part = str(application_id)
        rel = f"{app_part}/{safe}"
        dest = self._root / app_part
        dest.mkdir(parents=True, exist_ok=True)
        full = self._root / rel
        full.write_bytes(data)
        return rel.replace("\\", "/")

    def absolute_path(self, storage_key: str) -> Path:
        return (self._root / storage_key).resolve()

    def read_bytes(self, storage_key: str) -> bytes:
        """Load file contents."""
        primary = self.absolute_path(storage_key)
        try:
            return primary.read_bytes()
        except FileNotFoundError:
            legacy = _LEGACY_APPS_API_UPLOADS / storage_key.replace("\\", "/")
            if legacy.is_file():
                return legacy.read_bytes()
            logger.error(
                "storage_read_failed storage_key=%s primary=%s legacy=%s legacy_dir_exists=%s",
                storage_key,
                primary,
                legacy,
                _LEGACY_APPS_API_UPLOADS.is_dir(),
            )
            raise

    def delete(self, storage_key: str) -> None:
        p = self.absolute_path(storage_key)
        if p.is_file():
            p.unlink()
            return
        legacy = _LEGACY_APPS_API_UPLOADS / storage_key.replace("\\", "/")
        if legacy.is_file():
            legacy.unlink()


def get_storage() -> LocalStorageBackend:
    from invision_api.core.config import get_settings

    root = get_settings().upload_root
    Path(root).mkdir(parents=True, exist_ok=True)
    return LocalStorageBackend(root)
