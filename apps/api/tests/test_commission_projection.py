"""Integration tests for commission projection creation and field mapping."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from invision_api.models.enums import SectionKey
from invision_api.repositories.commission_repository import upsert_projection_for_application


def test_projection_populates_candidate_name(db: Session, factory):
    """Projection sets candidate_full_name from CandidateProfile."""
    user = factory.user(db)
    profile = factory.profile(db, user, first_name="Айдар", last_name="Сериков")
    app = factory.application(db, profile)
    db.flush()

    row = upsert_projection_for_application(db, app)
    assert row.candidate_full_name == "Айдар Сериков"
    assert row.application_id == app.id


def test_projection_populates_city_phone_from_contact(db: Session, factory):
    """Projection extracts city and phone from contact section payload."""
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    from invision_api.models.application import ApplicationSectionState
    db.add(ApplicationSectionState(
        application_id=app.id,
        section_key="contact",
        payload={"phone_e164": "+77051234567", "city": "Астана", "address_line1": "x", "country": "KZ"},
        is_complete=True,
        schema_version=1,
        last_saved_at=datetime.now(tz=UTC),
    ))
    db.flush()

    row = upsert_projection_for_application(db, app)
    assert row.city == "Астана"
    assert row.phone == "+77051234567"


def test_projection_updates_on_second_call(db: Session, factory):
    """Calling upsert twice updates existing projection."""
    user = factory.user(db)
    profile = factory.profile(db, user, first_name="A", last_name="B")
    app = factory.application(db, profile)
    db.flush()

    row1 = upsert_projection_for_application(db, app)
    assert row1.candidate_full_name == "A B"

    profile.first_name = "C"
    profile.last_name = "D"
    row2 = upsert_projection_for_application(db, app)
    assert row2.candidate_full_name == "C D"
    assert row1.application_id == row2.application_id


def test_projection_stage_follows_application(db: Session, factory):
    """Projection stage matches application current_stage."""
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    db.flush()

    row = upsert_projection_for_application(db, app)
    assert row.current_stage == "application"

    app.current_stage = "initial_screening"
    row = upsert_projection_for_application(db, app)
    assert row.current_stage == "initial_screening"
