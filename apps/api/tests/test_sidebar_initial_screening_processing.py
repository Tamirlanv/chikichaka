"""Sidebar returns processing panel (not LLM summary) on initial_screening."""

from __future__ import annotations

from sqlalchemy.orm import Session

from invision_api.commission.application import sidebar_service
from invision_api.models.enums import ApplicationStage, ApplicationState
from invision_api.services import candidate_activity_service


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


def test_get_sidebar_panel_engagement_on_initial_screening(db: Session, factory) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.under_screening.value)
    app.current_stage = ApplicationStage.initial_screening.value
    db.flush()

    panel = sidebar_service.get_sidebar_panel(db, application_id=app.id, tab="engagement")
    assert panel["type"] == "summary"
    assert panel["title"] == "Вовлеченность"
    assert [sec["title"] for sec in panel["sections"]] == ["Сигналы", "Интерпретация", "Итог"]
    lines = [item for sec in panel["sections"] for item in sec["items"]]
    all_text = " ".join(str(x).lower() for x in lines)
    assert "ключевые шаги:" not in all_text
    assert "возврат" not in all_text
    assert "редактирован" not in all_text
    assert "пройдены не полностью" not in all_text


def test_get_sidebar_panel_engagement_sections_human_readable(db: Session, factory) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.application_review.value
    db.flush()

    candidate_activity_service.record_candidate_activity_event(
        db,
        application_id=app.id,
        candidate_user_id=user.id,
        event_type="platform_interaction_ping",
    )
    db.flush()

    panel = sidebar_service.get_sidebar_panel(db, application_id=app.id, tab="engagement")
    assert panel["type"] == "summary"
    assert panel["title"] == "Вовлеченность"
    assert [sec["title"] for sec in panel["sections"]] == ["Сигналы", "Интерпретация", "Итог"]
    assert len(panel["sections"][0]["items"]) >= 6
