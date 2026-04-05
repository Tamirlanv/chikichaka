"""Sidebar returns processing panel (not LLM summary) on initial_screening."""

from __future__ import annotations

from sqlalchemy.orm import Session

from invision_api.commission.application import sidebar_service
from invision_api.models.enums import ApplicationStage, ApplicationState


def test_get_sidebar_panel_processing_on_initial_screening(db: Session, factory) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.under_screening.value)
    app.current_stage = ApplicationStage.initial_screening.value
    db.flush()

    panel = sidebar_service.get_sidebar_panel(db, application_id=app.id, tab="motivation")
    assert panel["type"] == "processing"
    assert panel["title"] == "Статус обработки"
    for sec in panel["sections"]:
        assert sec["title"] != "Краткий итог"


def test_get_sidebar_panel_initial_screening_wins_over_ai_interview_tab(db: Session, factory) -> None:
    """tab=ai_interview must not return LLM resolution panel while still on initial_screening."""
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.under_screening.value)
    app.current_stage = ApplicationStage.initial_screening.value
    db.flush()

    panel = sidebar_service.get_sidebar_panel(db, application_id=app.id, tab="ai_interview")
    assert panel["type"] == "processing"
    assert panel["title"] == "Статус обработки"
    for sec in panel["sections"]:
        assert sec["title"] != "Краткий итог"
