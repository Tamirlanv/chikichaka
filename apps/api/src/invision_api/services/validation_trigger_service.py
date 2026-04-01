"""Fire-and-forget trigger for the candidate-validation-orchestrator after submit."""

from __future__ import annotations

import logging
import os
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)

ORCHESTRATOR_URL = os.getenv("VALIDATION_ORCHESTRATOR_URL", "http://localhost:4500")


def trigger_validation_run(
    *,
    application_id: UUID,
    candidate_id: UUID,
) -> None:
    """Non-blocking call to the orchestrator. Failures are logged but never propagate."""
    url = f"{ORCHESTRATOR_URL}/candidate-validation/runs"
    payload = {
        "applicationId": str(application_id),
        "candidateId": str(candidate_id),
        "checks": ["links", "videoPresentation", "certificates"],
    }
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code < 300:
                logger.info("Validation run triggered for application %s: %s", application_id, resp.json().get("runId", "?"))
            else:
                logger.warning("Orchestrator returned %s for application %s: %s", resp.status_code, application_id, resp.text[:200])
    except Exception:
        logger.warning("Failed to trigger validation orchestrator for application %s (service may be offline)", application_id, exc_info=True)
