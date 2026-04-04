"""AI clarification interview: weights, gating, approve flow, candidate DTO."""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from invision_api.commission.application import service as commission_service
from invision_api.commission.application import sidebar_service
from invision_api.models.commission import InterviewSlotBooking
from invision_api.models.enums import ApplicationStage, ApplicationState
from invision_api.repositories import ai_interview_repository, commission_repository
from invision_api.services.ai_interview.prioritize import compute_signal_weight, question_count_from_weight
from invision_api.services.ai_interview import service as ai_interview_service
from invision_api.services.interview_preferences import service as interview_preferences_service
from invision_api.services.stages import application_review_service


def test_question_count_bands() -> None:
    assert question_count_from_weight(0) == 3
    assert question_count_from_weight(4) == 3
    assert question_count_from_weight(5) == 4
    assert question_count_from_weight(8) == 4
    assert question_count_from_weight(9) == 5


def test_weight_from_signals() -> None:
    summary = {
        "contradictions": [{"severity": "high"}, {"severity": "medium"}],
        "attention_flags": ["a"],
    }
    w = compute_signal_weight(summary)
    assert w >= 3


def test_advance_stage_blocked_from_application_review(db: Session, factory) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.application_review.value
    app.state = ApplicationState.under_review.value
    app.locked_after_submit = True
    db.flush()

    with pytest.raises(HTTPException) as exc:
        commission_service.advance_stage(db, app.id, user.id, None)
    assert exc.value.status_code == 409


def test_approve_without_draft_returns_409(db: Session, factory) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.application_review.value
    app.state = ApplicationState.under_review.value
    db.flush()

    with pytest.raises(HTTPException) as exc:
        ai_interview_service.approve_ai_interview(db, app.id, actor_user_id=user.id)
    assert exc.value.status_code == 409


def test_approve_transitions_to_interview(db: Session, factory) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.application_review.value
    app.state = ApplicationState.under_review.value
    db.flush()

    questions = [
        {"id": "q1", "questionText": "Первый вопрос?", "sortOrder": 0},
        {"id": "q2", "questionText": "Второй вопрос?", "sortOrder": 1},
        {"id": "q3", "questionText": "Третий вопрос?", "sortOrder": 2},
    ]
    ai_interview_repository.upsert_draft(
        db,
        application_id=app.id,
        questions=questions,
        generated_from_signals={"test": True},
    )

    ai_interview_service.approve_ai_interview(db, app.id, actor_user_id=user.id)
    db.refresh(app)
    assert app.current_stage == ApplicationStage.interview.value


def test_candidate_questions_contain_no_internal_fields(db: Session, factory) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.interview.value
    app.state = ApplicationState.interview_pending.value
    db.flush()

    questions = [
        {
            "id": "q1",
            "questionText": "Вопрос для кандидата",
            "reasonDescription": "секрет комиссии",
            "severity": "high",
            "sortOrder": 0,
        },
        {"id": "q2", "questionText": "Второй", "sortOrder": 1},
        {"id": "q3", "questionText": "Третий", "sortOrder": 2},
    ]
    row = ai_interview_repository.upsert_draft(
        db,
        application_id=app.id,
        questions=questions,
        generated_from_signals=None,
    )
    ai_interview_repository.mark_approved(db, row, approved_by_user_id=user.id)

    out = ai_interview_service.get_approved_questions_for_candidate(db, app.id)
    assert len(out) == 3
    for item in out:
        assert set(item.keys()) == {"id", "sortOrder", "questionText"}
        assert "reason" not in item
        assert "секрет" not in str(item)


def test_regenerate_draft_clears_approval_metadata(db: Session, factory) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.application_review.value
    app.state = ApplicationState.under_review.value
    db.flush()

    questions = [
        {"id": "q1", "questionText": "A?", "sortOrder": 0},
        {"id": "q2", "questionText": "B?", "sortOrder": 1},
        {"id": "q3", "questionText": "C?", "sortOrder": 2},
    ]
    row = ai_interview_repository.upsert_draft(
        db,
        application_id=app.id,
        questions=questions,
        generated_from_signals={"test": True},
    )
    ai_interview_repository.mark_approved(db, row, approved_by_user_id=user.id)
    db.refresh(row)
    assert row.approved_at is not None
    assert row.approved_by_user_id is not None

    ai_interview_repository.upsert_draft(
        db,
        application_id=app.id,
        questions=questions,
        generated_from_signals={"regen": True},
    )
    db.refresh(row)
    assert row.status == "draft"
    assert row.approved_at is None
    assert row.approved_by_user_id is None


def test_approve_idempotent_returns_flag(db: Session, factory) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.application_review.value
    app.state = ApplicationState.under_review.value
    db.flush()

    questions = [
        {"id": "q1", "questionText": "A?", "sortOrder": 0},
        {"id": "q2", "questionText": "B?", "sortOrder": 1},
        {"id": "q3", "questionText": "C?", "sortOrder": 2},
    ]
    ai_interview_repository.upsert_draft(
        db,
        application_id=app.id,
        questions=questions,
        generated_from_signals=None,
    )

    out1 = ai_interview_service.approve_ai_interview(db, app.id, actor_user_id=user.id)
    assert out1.get("alreadyApproved") is False
    db.refresh(app)

    out2 = ai_interview_service.approve_ai_interview(db, app.id, actor_user_id=user.id)
    assert out2.get("alreadyApproved") is True


def test_candidate_sees_commission_edited_text(db: Session, factory) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.interview.value
    app.state = ApplicationState.interview_pending.value
    db.flush()

    questions = [
        {
            "id": "q1",
            "questionText": "Оригинал",
            "commissionEditedText": "Текст после правки комиссии",
            "sortOrder": 0,
        },
        {"id": "q2", "questionText": "Второй", "sortOrder": 1},
        {"id": "q3", "questionText": "Третий", "sortOrder": 2},
    ]
    row = ai_interview_repository.upsert_draft(
        db,
        application_id=app.id,
        questions=questions,
        generated_from_signals=None,
    )
    ai_interview_repository.mark_approved(db, row, approved_by_user_id=user.id)

    out = ai_interview_service.get_approved_questions_for_candidate(db, app.id)
    q1 = next(x for x in out if x["id"] == "q1")
    assert q1["questionText"] == "Текст после правки комиссии"


def test_internal_transition_blocked_without_approved_ai(monkeypatch, db: Session, factory) -> None:
    monkeypatch.setattr(
        "invision_api.services.stages.application_review_service.get_settings",
        lambda: SimpleNamespace(ai_interview_allow_internal_transition_bypass=False),
    )
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.application_review.value
    app.state = ApplicationState.under_review.value
    db.flush()

    with pytest.raises(ValueError, match="одобрения"):
        application_review_service.transition_to_interview(db, app, actor_user_id=user.id)


def test_internal_transition_allowed_with_approved_set(monkeypatch, db: Session, factory) -> None:
    monkeypatch.setattr(
        "invision_api.services.stages.application_review_service.get_settings",
        lambda: SimpleNamespace(ai_interview_allow_internal_transition_bypass=False),
    )
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.application_review.value
    app.state = ApplicationState.under_review.value
    db.flush()

    questions = [
        {"id": "q1", "questionText": "A?", "sortOrder": 0},
        {"id": "q2", "questionText": "B?", "sortOrder": 1},
        {"id": "q3", "questionText": "C?", "sortOrder": 2},
    ]
    row = ai_interview_repository.upsert_draft(
        db,
        application_id=app.id,
        questions=questions,
        generated_from_signals=None,
    )
    ai_interview_repository.mark_approved(db, row, approved_by_user_id=user.id)

    application_review_service.transition_to_interview(db, app, actor_user_id=user.id)
    db.refresh(app)
    assert app.current_stage == ApplicationStage.interview.value


def test_internal_transition_bypass_flag_skips_ai_guard(monkeypatch, db: Session, factory) -> None:
    mock_settings = SimpleNamespace(
        ai_interview_allow_internal_transition_bypass=True,
        environment="local",
    )
    monkeypatch.setattr(
        "invision_api.services.stages.application_review_service.get_settings",
        lambda: mock_settings,
    )
    monkeypatch.setattr(
        "invision_api.services.stage_transition_policy.get_settings",
        lambda: mock_settings,
    )
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.application_review.value
    app.state = ApplicationState.under_review.value
    db.flush()

    application_review_service.transition_to_interview(db, app, actor_user_id=user.id)
    db.refresh(app)
    assert app.current_stage == ApplicationStage.interview.value


def test_internal_transition_bypass_rejected_in_production(monkeypatch, db: Session, factory) -> None:
    mock_settings = SimpleNamespace(
        ai_interview_allow_internal_transition_bypass=True,
        environment="production",
    )
    monkeypatch.setattr(
        "invision_api.services.stages.application_review_service.get_settings",
        lambda: mock_settings,
    )
    monkeypatch.setattr(
        "invision_api.services.stage_transition_policy.get_settings",
        lambda: mock_settings,
    )
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.application_review.value
    app.state = ApplicationState.under_review.value
    db.flush()

    with pytest.raises(ValueError, match="production"):
        application_review_service.transition_to_interview(db, app, actor_user_id=user.id)


def test_generate_requires_data_ready_when_configured(monkeypatch, db: Session, factory) -> None:
    monkeypatch.setattr(
        "invision_api.services.ai_interview.service.get_settings",
        lambda: SimpleNamespace(ai_interview_require_data_ready=True),
    )
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.application_review.value
    app.state = ApplicationState.under_review.value
    db.flush()

    with pytest.raises(HTTPException) as exc:
        ai_interview_service.generate_ai_interview_draft(db, app.id, actor_user_id=user.id)
    assert exc.value.status_code == 409


def test_patch_draft_audit_includes_changed_question_ids(monkeypatch, db: Session, factory) -> None:
    captured: list[dict] = []

    def spy(db_sess, **kwargs):
        if kwargs.get("event_type") == "ai_interview_draft_updated":
            captured.append(kwargs.get("metadata") or {})

    monkeypatch.setattr(
        "invision_api.services.ai_interview.service.commission_audit.write_event",
        spy,
    )

    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.application_review.value
    app.state = ApplicationState.under_review.value
    db.flush()

    questions = [
        {"id": "q1", "questionText": "Один?", "sortOrder": 0},
        {"id": "q2", "questionText": "Два?", "sortOrder": 1},
        {"id": "q3", "questionText": "Три?", "sortOrder": 2},
    ]
    row = ai_interview_repository.upsert_draft(
        db,
        application_id=app.id,
        questions=questions,
        generated_from_signals=None,
    )
    rev = row.revision

    updated = [
        {"id": "q1", "questionText": "Изменили только первый", "sortOrder": 0},
        {"id": "q2", "questionText": "Два?", "sortOrder": 1},
        {"id": "q3", "questionText": "Три?", "sortOrder": 2},
    ]
    ai_interview_service.patch_draft_questions(
        db, app.id, revision=rev, questions=updated, actor_user_id=user.id
    )
    assert captured and "q1" in (captured[0].get("question_ids_text_changed") or [])


def test_e2e_mock_generate_patch_approve_candidate_questions(monkeypatch, db: Session, factory) -> None:
    def fake_gen(*, context, target_count):
        base = [
            {"id": "a1", "questionText": "Вопрос один?", "sortOrder": 0},
            {"id": "a2", "questionText": "Вопрос два?", "sortOrder": 1},
            {"id": "a3", "questionText": "Вопрос три?", "sortOrder": 2},
        ]
        return base[:target_count], {"path": "test", "degraded": False}

    monkeypatch.setattr(
        "invision_api.services.ai_interview.service.generate_questions_llm",
        fake_gen,
    )

    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.application_review.value
    app.state = ApplicationState.under_review.value
    db.flush()

    gen_out = ai_interview_service.generate_ai_interview_draft(db, app.id, actor_user_id=user.id)
    assert "dataProcessingReady" in gen_out
    rev = gen_out["revision"]

    patched = [
        {**q, "commissionEditedText": "Правка " + (q.get("questionText") or "")}
        for q in gen_out["questions"]
    ]
    ai_interview_service.patch_draft_questions(
        db, app.id, revision=rev, questions=patched, actor_user_id=user.id
    )

    ai_interview_service.approve_ai_interview(db, app.id, actor_user_id=user.id)
    db.refresh(app)
    assert app.current_stage == ApplicationStage.interview.value

    cand = ai_interview_service.get_approved_questions_for_candidate(db, app.id)
    assert len(cand) == 3
    assert all("questionText" in x and "reason" not in x for x in cand)


@patch("invision_api.services.ai_interview.generation.OpenAIProvider")
def test_question_text_sanitized_when_llm_echoes_schema(mock_provider_cls, db: Session, factory) -> None:
    class _P:
        def committee_structured_summary(self, **kwargs):
            return {
                "questions": [
                    {
                        "questionText": "Опишите growth_journey и поле reasonDescription?",
                        "reasonType": "missing_context",
                        "reasonDescription": "x",
                        "sourceSections": ["growth_journey"],
                        "severity": "low",
                    },
                    {
                        "questionText": "Второй вопрос нормальный длины для теста?",
                        "reasonType": "missing_context",
                        "reasonDescription": "y",
                        "sourceSections": [],
                        "severity": "low",
                    },
                    {
                        "questionText": "Третий вопрос тоже нормальный?",
                        "reasonType": "missing_context",
                        "reasonDescription": "z",
                        "sourceSections": [],
                        "severity": "low",
                    },
                ]
            }

    mock_provider_cls.return_value = _P()

    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.application_review.value
    app.state = ApplicationState.under_review.value
    db.flush()

    out = ai_interview_service.generate_ai_interview_draft(db, app.id, actor_user_id=user.id)
    texts = [q.get("questionText") or "" for q in out["questions"]]
    assert not any("growth_journey" in t.lower() for t in texts)
    assert not any("reasonDescription" in t for t in texts)


def test_list_candidate_answers_after_save(db: Session, factory) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.interview.value
    app.state = ApplicationState.interview_pending.value
    db.flush()

    questions = [
        {"id": "q1", "questionText": "Один?", "sortOrder": 0},
        {"id": "q2", "questionText": "Два?", "sortOrder": 1},
        {"id": "q3", "questionText": "Три?", "sortOrder": 2},
    ]
    row = ai_interview_repository.upsert_draft(
        db,
        application_id=app.id,
        questions=questions,
        generated_from_signals=None,
    )
    ai_interview_repository.mark_approved(db, row, approved_by_user_id=user.id)

    ai_interview_service.save_candidate_answers_stub(
        db,
        app.id,
        answers=[{"questionId": "q1", "text": "Ответ на первый"}],
    )
    db.commit()

    listed = ai_interview_service.list_candidate_answers_for_application(db, app.id)
    assert len(listed) == 1
    assert listed[0]["questionId"] == "q1"
    assert listed[0]["text"] == "Ответ на первый"
    assert listed[0].get("updatedAt")


def test_complete_ai_interview_fails_when_answers_incomplete(db: Session, factory) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.interview.value
    app.state = ApplicationState.interview_pending.value
    db.flush()

    questions = [
        {"id": "q1", "questionText": "Один?", "sortOrder": 0},
        {"id": "q2", "questionText": "Два?", "sortOrder": 1},
        {"id": "q3", "questionText": "Три?", "sortOrder": 2},
    ]
    row = ai_interview_repository.upsert_draft(
        db,
        application_id=app.id,
        questions=questions,
        generated_from_signals=None,
    )
    ai_interview_repository.mark_approved(db, row, approved_by_user_id=user.id)

    ai_interview_service.save_candidate_answers_stub(
        db,
        app.id,
        answers=[{"questionId": "q1", "text": "Только первый"}],
    )
    db.flush()

    with pytest.raises(HTTPException) as exc:
        ai_interview_service.complete_candidate_ai_interview(db, app.id)
    assert exc.value.status_code == 422


@patch("invision_api.services.ai_interview.resolution_summary.generate_resolution_summary_llm")
def test_complete_ai_interview_idempotent(mock_llm, db: Session, factory) -> None:
    mock_llm.return_value = {
        "shortSummary": "Кратко.",
        "resolvedPoints": ["a"],
        "unresolvedPoints": [],
        "newInformation": [],
        "confidence": "medium",
        "generatedAt": datetime.now(tz=UTC).isoformat(),
        "promptVersion": "resolution_summary_v1",
    }
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.interview.value
    app.state = ApplicationState.interview_pending.value
    db.flush()

    questions = [
        {"id": "q1", "questionText": "Один?", "sortOrder": 0},
        {"id": "q2", "questionText": "Два?", "sortOrder": 1},
        {"id": "q3", "questionText": "Три?", "sortOrder": 2},
    ]
    row = ai_interview_repository.upsert_draft(
        db,
        application_id=app.id,
        questions=questions,
        generated_from_signals=None,
    )
    ai_interview_repository.mark_approved(db, row, approved_by_user_id=user.id)

    ai_interview_service.save_candidate_answers_stub(
        db,
        app.id,
        answers=[
            {"questionId": "q1", "text": "A"},
            {"questionId": "q2", "text": "B"},
            {"questionId": "q3", "text": "C"},
        ],
    )
    db.flush()

    out1 = ai_interview_service.complete_candidate_ai_interview(db, app.id)
    assert out1.get("alreadyCompleted") is False
    assert mock_llm.called
    out2 = ai_interview_service.complete_candidate_ai_interview(db, app.id)
    assert out2.get("alreadyCompleted") is True
    assert mock_llm.call_count == 1


@patch("invision_api.services.ai_interview.resolution_summary.generate_resolution_summary_llm")
def test_resolution_summary_persisted_and_read_models(mock_llm, db: Session, factory) -> None:
    mock_llm.return_value = {
        "shortSummary": "Итог для комиссии.",
        "resolvedPoints": ["п.1"],
        "unresolvedPoints": ["п.2"],
        "newInformation": ["п.3"],
        "confidence": "high",
        "generatedAt": datetime.now(tz=UTC).isoformat(),
        "promptVersion": "resolution_summary_v1",
    }
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.interview.value
    app.state = ApplicationState.interview_pending.value
    db.flush()

    questions = [
        {"id": "q1", "questionText": "Один?", "sortOrder": 0},
        {"id": "q2", "questionText": "Два?", "sortOrder": 1},
        {"id": "q3", "questionText": "Три?", "sortOrder": 2},
    ]
    row = ai_interview_repository.upsert_draft(
        db,
        application_id=app.id,
        questions=questions,
        generated_from_signals=None,
    )
    ai_interview_repository.mark_approved(db, row, approved_by_user_id=user.id)
    ai_interview_service.save_candidate_answers_stub(
        db,
        app.id,
        answers=[
            {"questionId": "q1", "text": "A"},
            {"questionId": "q2", "text": "B"},
            {"questionId": "q3", "text": "C"},
        ],
    )
    db.flush()

    ai_interview_service.complete_candidate_ai_interview(db, app.id)
    db.refresh(row)
    assert row.resolution_summary and row.resolution_summary.get("shortSummary") == "Итог для комиссии."
    assert row.resolution_summary_error is None

    view = ai_interview_service.build_commission_ai_interview_session_view(db, app.id)
    assert view["resolutionSummary"]["shortSummary"] == "Итог для комиссии."
    assert view["resolutionSummaryError"] is None

    panel = sidebar_service.get_sidebar_panel(db, application_id=app.id, tab="ai_interview")
    assert panel["type"] == "summary"
    titles = [s["title"] for s in panel["sections"]]
    assert "Краткий итог" in titles
    assert "Что удалось уточнить" in titles


@patch("invision_api.services.ai_interview.resolution_summary.generate_resolution_summary_llm")
def test_complete_succeeds_when_resolution_llm_fails(mock_llm, db: Session, factory) -> None:
    mock_llm.side_effect = RuntimeError("llm_down")
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.interview.value
    app.state = ApplicationState.interview_pending.value
    db.flush()

    questions = [
        {"id": "q1", "questionText": "Один?", "sortOrder": 0},
        {"id": "q2", "questionText": "Два?", "sortOrder": 1},
        {"id": "q3", "questionText": "Три?", "sortOrder": 2},
    ]
    row = ai_interview_repository.upsert_draft(
        db,
        application_id=app.id,
        questions=questions,
        generated_from_signals=None,
    )
    ai_interview_repository.mark_approved(db, row, approved_by_user_id=user.id)
    ai_interview_service.save_candidate_answers_stub(
        db,
        app.id,
        answers=[
            {"questionId": "q1", "text": "A"},
            {"questionId": "q2", "text": "B"},
            {"questionId": "q3", "text": "C"},
        ],
    )
    db.flush()

    out = ai_interview_service.complete_candidate_ai_interview(db, app.id)
    assert out.get("alreadyCompleted") is False
    db.refresh(row)
    assert row.resolution_summary is None
    err = (row.resolution_summary_error or "").strip()
    assert err
    assert "llm_down" not in err.lower()
    assert "администратору" in err.lower() or "позже" in err.lower()


def test_interview_preferences_blocked_until_ai_interview_completed(db: Session, factory) -> None:
    """Days/slots endpoints require approved question set and candidate_completed_at."""
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = ApplicationStage.interview.value
    app.state = ApplicationState.interview_pending.value
    db.flush()

    questions = [{"id": "q1", "questionText": "A?", "sortOrder": 0}]
    row = ai_interview_repository.upsert_draft(
        db,
        application_id=app.id,
        questions=questions,
        generated_from_signals=None,
    )
    ai_interview_repository.mark_approved(db, row, approved_by_user_id=user.id)
    db.flush()

    with pytest.raises(HTTPException) as exc:
        interview_preferences_service.list_available_days(db, app.id)
    assert exc.value.status_code == 409
    assert "завершите" in str(exc.value.detail).lower()

    with pytest.raises(HTTPException) as exc:
        interview_preferences_service.list_available_slots_for_date(db, app.id, date(2030, 6, 4))
    assert exc.value.status_code == 409

    with pytest.raises(HTTPException) as exc:
        interview_preferences_service.submit_interview_preferences(
            db,
            app.id,
            slots=[{"date": "2030-06-04", "timeRangeCode": "09-11"}],
        )
    assert exc.value.status_code == 409


def test_submit_interview_preferences_conflict_returns_409(db: Session, factory) -> None:
    """Second application cannot book the same (date, time_range_code) as an existing booking."""
    slot_d = date(2030, 6, 4)
    assert slot_d.weekday() < 5

    u1 = factory.user(db)
    p1 = factory.profile(db, u1)
    app1 = factory.application(db, p1, state=ApplicationState.submitted.value)
    app1.current_stage = ApplicationStage.interview.value
    app1.state = ApplicationState.interview_pending.value
    db.flush()

    u2 = factory.user(db)
    p2 = factory.profile(db, u2)
    app2 = factory.application(db, p2, state=ApplicationState.submitted.value)
    app2.current_stage = ApplicationStage.interview.value
    app2.state = ApplicationState.interview_pending.value
    db.flush()

    q_rows = [
        {"id": "q1", "questionText": "A?", "sortOrder": 0},
        {"id": "q2", "questionText": "B?", "sortOrder": 1},
        {"id": "q3", "questionText": "C?", "sortOrder": 2},
    ]
    row2 = ai_interview_repository.upsert_draft(
        db,
        application_id=app2.id,
        questions=q_rows,
        generated_from_signals=None,
    )
    ai_interview_repository.mark_approved(db, row2, approved_by_user_id=u2.id)
    row2.candidate_completed_at = datetime.now(tz=UTC)
    db.flush()

    db.add(
        InterviewSlotBooking(
            application_id=app1.id,
            slot_date=slot_d,
            time_range_code="09-11",
            sort_order=1,
        )
    )
    db.flush()

    with pytest.raises(HTTPException) as exc:
        interview_preferences_service.submit_interview_preferences(
            db,
            app2.id,
            slots=[{"date": slot_d.isoformat(), "timeRangeCode": "09-11"}],
        )
    assert exc.value.status_code == 409


def test_list_projections_interview_kanban_only_filters_by_preferences(db: Session, factory) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app_ready = factory.application(db, profile, state=ApplicationState.submitted.value)
    app_ready.current_stage = ApplicationStage.interview.value
    app_ready.state = ApplicationState.interview_pending.value
    app_ready.interview_preferences_submitted_at = datetime.now(tz=UTC)
    db.flush()

    user2 = factory.user(db)
    profile2 = factory.profile(db, user2)
    app_pending = factory.application(db, profile2, state=ApplicationState.submitted.value)
    app_pending.current_stage = ApplicationStage.interview.value
    app_pending.state = ApplicationState.interview_pending.value
    app_pending.interview_preferences_submitted_at = None
    db.flush()

    commission_repository.upsert_projection_for_application(db, app_ready)
    commission_repository.upsert_projection_for_application(db, app_pending)

    rows = commission_repository.list_projections(
        db,
        stage=ApplicationStage.interview.value,
        interview_kanban_only=True,
        limit=50,
    )
    ids = {r.application_id for r in rows}
    assert app_ready.id in ids
    assert app_pending.id not in ids
