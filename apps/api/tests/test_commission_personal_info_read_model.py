from datetime import UTC, datetime
from sqlalchemy.orm import Session

from invision_api.commission.application.personal_info_service import get_commission_application_personal_info
from invision_api.models.application import AdmissionDecision, ApplicationSectionState
from invision_api.models.commission import CommissionUser
from invision_api.models.enums import ApplicationState


def test_personal_info_read_model_sections_are_mapped(db: Session, factory):
    committee_user = factory.user(db)
    committee_role = factory.committee_role(db)
    factory.assign_role(db, committee_user, committee_role)
    db.add(CommissionUser(user_id=committee_user.id, role="reviewer"))

    candidate_user = factory.user(db)
    profile = factory.profile(db, candidate_user, first_name="Иван", last_name="Иванов")
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = "application_review"
    app.locked_after_submit = True
    app.submitted_at = datetime.now(tz=UTC)

    db.add(
        ApplicationSectionState(
            application_id=app.id,
            section_key="personal",
            payload={
                "preferred_first_name": "Иван",
                "preferred_last_name": "Иванов",
                "middle_name": "Иванович",
                "gender": "Мужской",
                "date_of_birth": "2007-04-10",
                "father_last": "Иванов",
                "father_first": "Петр",
                "father_phone": "+77010000001",
                "mother_last": "Иванова",
                "mother_first": "Мария",
                "mother_phone": "+77010000002",
            },
            is_complete=True,
            schema_version=1,
            last_saved_at=datetime.now(tz=UTC),
        )
    )
    db.add(
        ApplicationSectionState(
            application_id=app.id,
            section_key="contact",
            payload={
                "phone_e164": "+77029590338",
                "instagram": "@ivan",
                "telegram": "@ivannnnn3",
                "whatsapp": "+77029590338",
                "country": "KZ",
                "region": "Алматы",
                "city": "Алматы",
                "address_line1": "Алматы, Абая 15, кв 43",
            },
            is_complete=True,
            schema_version=1,
            last_saved_at=datetime.now(tz=UTC),
        )
    )
    db.add(
        ApplicationSectionState(
            application_id=app.id,
            section_key="education",
            payload={"presentation_video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
            is_complete=True,
            schema_version=1,
            last_saved_at=datetime.now(tz=UTC),
        )
    )
    db.flush()

    view = get_commission_application_personal_info(db, application_id=app.id, actor=committee_user)

    assert view["applicationId"] == str(app.id)
    assert view["candidateSummary"]["fullName"] == "Иван Иванов"
    assert view["candidateSummary"]["currentStage"] == "application_review"
    assert view["personalInfo"]["basicInfo"]["gender"] == "Мужской"
    assert view["personalInfo"]["basicInfo"]["birthDate"] == "2007-04-10"
    assert view["personalInfo"]["contacts"]["telegram"] == "@ivannnnn3"
    assert view["personalInfo"]["address"]["fullAddress"] == "Алматы, Абая 15, кв 43"
    assert len(view["personalInfo"]["guardians"]) == 2
    assert view["personalInfo"]["videoPresentation"]["url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert view["actions"]["canComment"] is True
    # Reviewer may open the advance flow on application_review; POST advance still enforces guards.
    assert view["actions"]["canMoveForward"] is True
    assert view["actions"]["canGenerateAiInterview"] is True


def test_personal_info_final_decision_forces_read_only(db: Session, factory) -> None:
    reviewer_user = factory.user(db)
    committee_role = factory.committee_role(db)
    factory.assign_role(db, reviewer_user, committee_role)
    db.add(CommissionUser(user_id=reviewer_user.id, role="reviewer"))

    candidate_user = factory.user(db)
    profile = factory.profile(db, candidate_user, first_name="Нурбек", last_name="Т.")
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = "result"
    app.locked_after_submit = True
    app.submitted_at = datetime.now(tz=UTC)
    db.add(
        AdmissionDecision(
            application_id=app.id,
            final_decision_status="reject",
            decision_at=datetime.now(tz=UTC),
            issued_by_user_id=reviewer_user.id,
        )
    )
    db.flush()

    view = get_commission_application_personal_info(db, application_id=app.id, actor=reviewer_user)

    assert view["readOnly"] is True
    assert view["actions"]["canComment"] is False
    assert view["actions"]["canMoveForward"] is False
    assert "финальное решение" in str(view.get("readOnlyReason", "")).lower()
