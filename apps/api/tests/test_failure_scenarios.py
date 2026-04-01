"""Pipeline test: failure scenarios and edge cases."""

import pytest
from sqlalchemy.orm import Session

from invision_api.models.enums import SectionKey
from invision_api.services.application_service import save_section, submit_application


def test_submit_with_invalid_section_data(db: Session, factory):
    """Submit fails when a section has invalid data (incomplete)."""
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="in_progress")
    db.commit()

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        submit_application(db, user)
    assert exc.value.status_code == 400


def test_save_section_invalid_payload_raises(db: Session, factory):
    """Saving with invalid payload data raises validation error."""
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    db.commit()

    with pytest.raises(Exception):
        save_section(db, user, SectionKey.personal, {
            "preferred_first_name": "",
            "preferred_last_name": "",
        })


def test_locked_app_rejects_all_section_saves(db: Session, factory):
    """Post-submit lock prevents saving any section."""
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    app.locked_after_submit = True
    db.commit()

    from fastapi import HTTPException
    sections_to_try = [
        (SectionKey.personal, {"preferred_first_name": "X", "preferred_last_name": "Y"}),
        (SectionKey.contact, {"phone_e164": "+77001111111", "address_line1": "x", "city": "y", "country": "KZ"}),
        (SectionKey.achievements_activities, {"activities": [{"category": "a", "title": "b"}]}),
    ]
    for key, payload in sections_to_try:
        with pytest.raises(HTTPException) as exc:
            save_section(db, user, key, payload)
        assert exc.value.status_code == 409, f"Section {key.value} should be rejected with 409"


def test_submit_not_possible_without_profile(db: Session, factory):
    """Submit without a candidate profile raises 404."""
    user = factory.user(db)
    db.commit()

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        submit_application(db, user)
    assert exc.value.status_code == 404
