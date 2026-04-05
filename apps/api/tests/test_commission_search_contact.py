"""Search in commission projections matches contact section (telegram, phone digits)."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from invision_api.models.application import ApplicationSectionState
from invision_api.repositories.commission_repository import list_projections, upsert_projection_for_application


def test_search_finds_candidate_by_telegram_handle_without_at(db: Session, factory):
    handle = f"officialmoosun_{uuid4().hex[:10]}"
    user = factory.user(db)
    profile = factory.profile(db, user, first_name="Иван", last_name="Иванов")
    app = factory.application(db, profile)
    db.add(
        ApplicationSectionState(
            application_id=app.id,
            section_key="contact",
            payload={
                "phone_e164": "+77001112233",
                "telegram": handle,
                "city": "Алматы",
                "country": "KZ",
            },
            is_complete=True,
            schema_version=1,
            last_saved_at=datetime.now(tz=UTC),
        )
    )
    db.flush()
    upsert_projection_for_application(db, app)
    db.flush()

    rows = list_projections(db, stage=None, stage_status=None, attention_only=False, program=None, search=handle, limit=50, offset=0)
    ids = [r.application_id for r in rows]
    assert app.id in ids
    assert ids.count(app.id) == 1


def test_search_finds_candidate_by_telegram_with_at_prefix(db: Session, factory):
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    db.add(
        ApplicationSectionState(
            application_id=app.id,
            section_key="contact",
            payload={"telegram": "@findme_handle", "city": "Алматы", "country": "KZ"},
            is_complete=True,
            schema_version=1,
            last_saved_at=datetime.now(tz=UTC),
        )
    )
    db.flush()
    upsert_projection_for_application(db, app)
    db.flush()

    rows = list_projections(db, stage=None, stage_status=None, attention_only=False, program=None, search="findme_handle", limit=50, offset=0)
    assert len(rows) == 1


def test_search_phone_digits_normalized(db: Session, factory):
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    db.add(
        ApplicationSectionState(
            application_id=app.id,
            section_key="contact",
            payload={"phone_e164": "+7 (705) 123-45-67", "city": "Алматы", "country": "KZ"},
            is_complete=True,
            schema_version=1,
            last_saved_at=datetime.now(tz=UTC),
        )
    )
    db.flush()
    upsert_projection_for_application(db, app)
    db.flush()

    rows = list_projections(db, stage=None, stage_status=None, attention_only=False, program=None, search="77051234567", limit=50, offset=0)
    assert len(rows) == 1


def test_search_instagram_partial(db: Session, factory):
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    db.add(
        ApplicationSectionState(
            application_id=app.id,
            section_key="contact",
            payload={"instagram": "@unique_insta_user", "city": "Алматы", "country": "KZ"},
            is_complete=True,
            schema_version=1,
            last_saved_at=datetime.now(tz=UTC),
        )
    )
    db.flush()
    upsert_projection_for_application(db, app)
    db.flush()

    rows = list_projections(db, stage=None, stage_status=None, attention_only=False, program=None, search="unique_insta", limit=50, offset=0)
    assert len(rows) == 1
