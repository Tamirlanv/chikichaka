"""Optional gate: data-check pipeline must be ready before AI interview generation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.enums import DataCheckRunStatus, DataCheckUnitType
from invision_api.repositories import data_check_repository
from invision_api.services.data_check.status_service import compute_run_status


def get_data_check_overall_status(db: Session, application_id: UUID) -> str | None:
    """Returns aggregate data-check status string, or None if no run/checks."""
    run = data_check_repository.resolve_preferred_run_for_application(db, application_id)
    if not run:
        return None
    checks = data_check_repository.list_checks_for_run(db, run.id)
    if not checks:
        return None
    status_map: dict[DataCheckUnitType, str] = {}
    for c in checks:
        try:
            status_map[DataCheckUnitType(c.check_type)] = c.status
        except ValueError:
            continue
    return compute_run_status(status_map).status


def is_data_processing_ready(db: Session, application_id: UUID) -> bool:
    return get_data_check_overall_status(db, application_id) == DataCheckRunStatus.ready.value
