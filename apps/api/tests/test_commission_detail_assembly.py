"""Integration tests for commission detail payload assembly."""

import pytest
from sqlalchemy.orm import Session

from invision_api.models.enums import SectionKey
from invision_api.repositories.commission_repository import upsert_projection_for_application


def test_detail_contains_all_section_keys(db: Session, factory):
    """After filling all sections, the detail view should include all section keys."""
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    factory.fill_required_sections(db, app)
    db.flush()

    sections = {ss.section_key for ss in app.section_states}
    expected = {k.value for k in SectionKey}
    assert expected.issubset(sections), f"Missing sections: {expected - sections}"


def test_detail_projection_has_submitted_at(db: Session, factory):
    """After submit, projection should have submitted_at set."""
    from datetime import UTC, datetime
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    app.submitted_at = datetime.now(tz=UTC)
    app.current_stage = "initial_screening"
    db.flush()

    row = upsert_projection_for_application(db, app)
    assert row.submitted_at is not None
    assert row.current_stage == "initial_screening"


def test_detail_candidate_name_not_null(db: Session, factory):
    """Commission detail candidate block must have non-null name."""
    user = factory.user(db)
    profile = factory.profile(db, user, first_name="Алия", last_name="Нурланова")
    app = factory.application(db, profile)
    db.flush()

    row = upsert_projection_for_application(db, app)
    assert row.candidate_full_name == "Алия Нурланова"
    assert row.candidate_full_name is not None
    assert len(row.candidate_full_name.strip()) > 0
