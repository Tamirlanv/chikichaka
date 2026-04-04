from __future__ import annotations

import os
from typing import Any
from uuid import UUID

import httpx

ORCHESTRATOR_URL = os.getenv("VALIDATION_ORCHESTRATOR_URL", "http://localhost:4500")


class ValidationOrchestratorClient:
    """HTTP client for candidate-validation-orchestrator (expects nested `checks` object)."""

    def __init__(self, base_url: str | None = None, *, timeout_sec: float = 6.0) -> None:
        self._base_url = (base_url or ORCHESTRATOR_URL).rstrip("/")
        self._timeout = timeout_sec

    def create_run(
        self,
        *,
        application_id: UUID,
        candidate_id: UUID,
        checks: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Submit a validation run. `checks` matches Fastify schema, e.g. `{"links": {"url": "..."}}`."""
        url = f"{self._base_url}/candidate-validation/runs"
        payload: dict[str, Any] = {
            "applicationId": str(application_id),
            "candidateId": str(candidate_id),
            "checks": checks or {},
        }
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(url, json=payload)
            if resp.status_code >= 300:
                return None
            try:
                data = resp.json()
            except Exception:  # noqa: BLE001
                return None
            return data if isinstance(data, dict) else None

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        url = f"{self._base_url}/candidate-validation/runs/{run_id}"
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(url)
            if resp.status_code >= 300:
                return None
            try:
                data = resp.json()
            except Exception:  # noqa: BLE001
                return None
            return data if isinstance(data, dict) else None
