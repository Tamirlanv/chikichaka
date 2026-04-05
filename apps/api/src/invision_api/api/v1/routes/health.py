from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from invision_api.core.redis_client import redis_ping
from invision_api.db.session import get_db

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok and redis_ping() else "degraded",
        "database": "ok" if db_ok else "error",
        "redis": "ok" if redis_ping() else "error",
    }


# ---------------------------------------------------------------------------
# Pipeline health — deeper check covering DB, Redis, validation services,
# and data-integrity metrics (projection coverage).
# ---------------------------------------------------------------------------


def _check_db(db: Session) -> dict[str, Any]:
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:200]}


def _check_redis() -> dict[str, Any]:
    try:
        ok = redis_ping()
        return {"status": "ok" if ok else "error"}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:200]}


def _check_service(name: str, url: str | None) -> dict[str, Any]:
    if not url:
        return {"status": "not_configured"}
    try:
        resp = httpx.get(url, timeout=3.0)
        ok = 200 <= resp.status_code < 300
        return {"status": "ok" if ok else "degraded", "http_status": resp.status_code}
    except Exception:
        return {"status": "unreachable"}


def _health_url_from_validate_url(validate_url: str) -> str:
    """Map .../certificate-validation/validate -> .../health (same origin)."""
    p = urlparse(validate_url)
    return urlunparse((p.scheme, p.netloc, "/health", "", "", ""))


def _certificate_validation_health_url() -> str:
    explicit = os.getenv("CERTIFICATE_VALIDATION_HEALTH_URL")
    if explicit:
        return explicit
    validate = os.getenv(
        "CERTIFICATE_VALIDATION_URL",
        "http://localhost:4400/certificate-validation/validate",
    )
    return _health_url_from_validate_url(validate)


def _count_projections_vs_submitted(db: Session) -> dict[str, Any]:
    try:
        submitted = db.execute(text("SELECT COUNT(*) FROM applications WHERE submitted_at IS NOT NULL")).scalar() or 0
        projections = db.execute(text("SELECT COUNT(*) FROM application_commission_projections")).scalar() or 0
        return {
            "submitted_applications": submitted,
            "commission_projections": projections,
            "gap": max(0, submitted - projections),
        }
    except Exception as e:
        return {"error": str(e)[:200]}


@router.get("/health/pipeline")
def pipeline_health(db: Session = Depends(get_db)) -> dict[str, Any]:
    """System health: DB, Redis, validation services, projection coverage."""
    orchestrator_url = (os.getenv("VALIDATION_ORCHESTRATOR_URL") or "").strip()
    link_health = (os.getenv("LINK_VALIDATION_HEALTH_URL") or "").strip()
    video_health = (os.getenv("VIDEO_VALIDATION_HEALTH_URL") or "").strip()
    cert_health = _certificate_validation_health_url()
    orchestrator_health_url = f"{orchestrator_url.rstrip('/')}/health" if orchestrator_url else None

    return {
        "database": _check_db(db),
        "redis": _check_redis(),
        "services": {
            "link_validation": _check_service("link_validation", link_health),
            "video_validation": _check_service("video_validation", video_health),
            "certificate_validation": _check_service("certificate_validation", cert_health),
            "orchestrator": _check_service("orchestrator", orchestrator_health_url),
        },
        "data_integrity": _count_projections_vs_submitted(db),
    }
