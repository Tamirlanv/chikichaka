"""Integration tests for initial screening pipeline."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.enums import ApplicationStage, ApplicationState, ScreeningResult
from invision_api.services.stages.initial_screening_service import (
    run_screening_checks_and_record,
)


def test_screening_passed_when_all_complete(db: Session, factory):
    """Screening passes when all sections are complete."""
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    app.current_stage = ApplicationStage.initial_screening.value
    factory.fill_required_sections(db, app)
    db.flush()

    result = run_screening_checks_and_record(db, app, actor_user_id=user.id)
    assert result.screening_result == ScreeningResult.passed.value


def test_screening_revision_required_when_incomplete(db: Session, factory):
    """Screening requires revision when sections are missing."""
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    app.current_stage = ApplicationStage.initial_screening.value
    db.flush()

    result = run_screening_checks_and_record(db, app, actor_user_id=user.id)
    assert result.screening_result == ScreeningResult.revision_required.value
    assert result.missing_items is not None
    assert len(result.missing_items.get("missing_sections", [])) > 0
