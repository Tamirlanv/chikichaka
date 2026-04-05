"""Regression tests for the Redis job worker payload handler."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from invision_api.models.enums import DataCheckUnitType, JobStatus, JobType
from invision_api.workers import job_worker


def test_process_payload_data_check_unit_resolves_admissions_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inner import in another branch must not shadow module-level admissions_repository (UnboundLocalError)."""
    mock_db = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.rollback = MagicMock()
    mock_db.close = MagicMock()

    monkeypatch.setattr(job_worker, "SessionLocal", lambda: mock_db)
    monkeypatch.setattr(
        job_worker.admissions_repository,
        "get_application_by_id",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(job_worker.job_runner_service, "run_unit", lambda *_a, **_k: None)

    payload = {
        "job_type": JobType.data_check_unit.value,
        "application_id": str(uuid4()),
        "analysis_job_id": str(uuid4()),
        "run_id": str(uuid4()),
        "unit_type": DataCheckUnitType.test_profile_processing.value,
    }

    job_worker.process_payload(payload)

    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()


def test_process_payload_run_block_analysis_marks_analysis_job_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_db = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.rollback = MagicMock()
    mock_db.close = MagicMock()

    job_id = uuid4()
    app_id = uuid4()
    job_row = MagicMock()
    updated = {"n": 0}

    def _get_analysis_job(_db, jid):
        assert jid == job_id
        return job_row

    def _update_analysis_job(_db, job, *, status=None, attempts=None, last_error=None):
        updated["n"] += 1
        assert status == JobStatus.completed.value

    monkeypatch.setattr(job_worker, "SessionLocal", lambda: mock_db)
    monkeypatch.setattr(job_worker.admissions_repository, "get_analysis_job", _get_analysis_job)
    monkeypatch.setattr(job_worker.admissions_repository, "update_analysis_job", _update_analysis_job)

    payload = {
        "job_type": JobType.run_block_analysis.value,
        "application_id": str(app_id),
        "analysis_job_id": str(job_id),
        "block_key": "motivation_goals",
    }

    job_worker.process_payload(payload)

    assert updated["n"] == 1
    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()
