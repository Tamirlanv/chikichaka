"""Tests for candidate stage transition emails (Resend)."""

from unittest.mock import patch
from uuid import uuid4

from sqlalchemy.orm import Session

from conftest import Factory
from invision_api.models.enums import ApplicationStage
from invision_api.services import candidate_stage_email_service
from invision_api.services.candidate_stage_email_service import send_stage_transition_notification


def test_send_stage_transition_skips_when_same_stage() -> None:
    with patch("invision_api.services.candidate_stage_email_service.send_html_email") as m:
        send_stage_transition_notification(uuid4(), ApplicationStage.initial_screening.value, ApplicationStage.initial_screening.value)
        m.assert_not_called()


def test_send_stage_transition_sends_when_stages_differ(db: Session) -> None:
    user = Factory.user(db)
    Factory.assign_role(db, user, Factory.candidate_role(db))
    profile = Factory.profile(db, user)
    app = Factory.application(db, profile)
    with patch("invision_api.services.candidate_stage_email_service.send_html_email", return_value=True) as m:
        candidate_stage_email_service.send_stage_transition_notification(
            app.id,
            ApplicationStage.application.value,
            ApplicationStage.initial_screening.value,
            db=db,
        )
    m.assert_called_once()
    assert m.call_args[0][0] == user.email


def test_send_final_decision_notification(db: Session) -> None:
    user = Factory.user(db)
    Factory.assign_role(db, user, Factory.candidate_role(db))
    profile = Factory.profile(db, user)
    app = Factory.application(db, profile)
    with patch("invision_api.services.candidate_stage_email_service.send_html_email", return_value=True) as m:
        candidate_stage_email_service.send_final_decision_notification(app.id, "enrolled", db=db)
    m.assert_called_once()
    assert "итог" in m.call_args[0][1].lower()
