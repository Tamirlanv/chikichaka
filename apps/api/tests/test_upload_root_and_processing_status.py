"""UPLOAD_ROOT resolution and data-check processing banner counts."""

from __future__ import annotations

from pathlib import Path
import pytest
from sqlalchemy.orm import Session

import invision_api.core.config as config_module
from invision_api.commission.application import personal_info_service
from invision_api.core.config import Settings
from invision_api.models.enums import DataCheckUnitType
from invision_api.repositories import data_check_repository
from invision_api.services.ai_interview.data_readiness import get_data_check_overall_status
from invision_api.services.data_check.status_service import TERMINAL_UNIT_STATUSES, UNIT_POLICIES
from invision_api.services.data_check import submit_bootstrap_service
from invision_api.services import storage as storage_module
from invision_api.services.storage import LocalStorageBackend


def _minimal_settings(**kwargs: object) -> Settings:
    base = {
        "database_url": "postgresql+psycopg://u:p@localhost:5432/db",
        "secret_key": "test-secret-key-not-for-production-0123456789",
    }
    base.update(kwargs)
    return Settings(**base)


def test_upload_root_relative_resolves_to_monorepo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UPLOAD_ROOT", raising=False)
    s = _minimal_settings(upload_root="./data/uploads")
    expected = (config_module._REPO_ROOT / "data" / "uploads").resolve()
    assert Path(s.upload_root).resolve() == expected


def test_upload_root_data_uploads_without_dot_same_as_dot_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UPLOAD_ROOT", raising=False)
    a = _minimal_settings(upload_root="./data/uploads")
    b = _minimal_settings(upload_root="data/uploads")
    assert Path(a.upload_root).resolve() == Path(b.upload_root).resolve()


def test_read_bytes_falls_back_to_legacy_apps_api_uploads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Files written under pre-anchor apps/api/data/uploads are still readable."""
    primary_root = tmp_path / "primary"
    primary_root.mkdir()
    legacy = tmp_path / "legacy"
    key = "708fdda5-4704-463d-b1f1-a04fc1563dcc/e6ca6cf8b10340288298b85672a9e5c6.jpeg"
    (legacy / Path(key).parent).mkdir(parents=True)
    (legacy / key).write_bytes(b"legacy-bytes")
    monkeypatch.setattr(storage_module, "_LEGACY_APPS_API_UPLOADS", legacy)

    backend = LocalStorageBackend(str(primary_root))
    assert backend.read_bytes(key) == b"legacy-bytes"


def test_upload_root_absolute_unchanged_except_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    """Absolute paths from env are only normalized with resolve() (env_file overrides kwargs)."""
    raw = "/tmp/invision_uploads_test_abs"
    monkeypatch.setenv("UPLOAD_ROOT", raw)
    s = _minimal_settings()
    assert Path(s.upload_root).resolve() == Path(raw).resolve()


def test_processing_status_counts_all_policy_units_when_checks_partial(
    db: Session, factory, monkeypatch
) -> None:
    """totalCount matches UNIT_POLICIES even when fewer CandidateValidationCheck rows exist."""
    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_a, **_kwargs: None)

    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    app.current_stage = "initial_screening"
    db.flush()

    run_id = submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )

    checks = data_check_repository.list_checks_for_run(db, run_id)
    assert len(checks) >= 3
    # Simulate incomplete bootstrap / missing rows: keep only first 3 checks
    for c in checks[3:]:
        db.delete(c)
    db.flush()

    remaining = data_check_repository.list_checks_for_run(db, run_id)
    assert len(remaining) == 3
    for c in remaining:
        c.status = "completed"
    db.flush()

    ps = personal_info_service._build_processing_status(db, app.id)
    assert ps is not None
    assert ps["totalCount"] == len(UNIT_POLICIES)
    assert ps["completedCount"] == 3
    assert ps["overall"] == "running"


def test_processing_status_completed_includes_failed_terminal(
    db: Session, factory, monkeypatch
) -> None:
    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_a, **_kwargs: None)

    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    app.current_stage = "initial_screening"
    db.flush()

    run_id = submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )

    checks = data_check_repository.list_checks_for_run(db, run_id)
    for i, c in enumerate(checks):
        c.status = "failed" if i == 0 else "completed"
    db.flush()

    ps = personal_info_service._build_processing_status(db, app.id)
    assert ps is not None
    assert ps["totalCount"] == len(UNIT_POLICIES)
    assert ps["completedCount"] == len(checks)
    for st in ps["units"].values():
        assert st in TERMINAL_UNIT_STATUSES or st == "pending"


def test_processing_status_overall_matches_kanban_aggregate(
    db: Session, factory, monkeypatch
) -> None:
    """processingStatus.overall and get_data_check_overall_status use the same compute_run_status input."""
    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_a, **_kwargs: None)

    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    app.current_stage = "initial_screening"
    db.flush()

    submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )

    ps = personal_info_service._build_processing_status(db, app.id)
    assert ps is not None
    kanban = get_data_check_overall_status(db, app.id)
    assert kanban is not None
    assert ps["overall"] == kanban
