"""Orchestration: context → weight → LLM draft, commission edits, approve + stage transition."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.commission.application import audit as commission_audit
from invision_api.commission.application.service import rebuild_projection
from invision_api.models.application import CandidateProfile
from invision_api.models.enums import ApplicationStage, InterviewPreferenceWindowStatus
from invision_api.repositories import ai_interview_repository
from invision_api.repositories import admissions_repository
from invision_api.services import audit_log_service, candidate_activity_service
from invision_api.core.config import get_settings
from invision_api.models.enums import DataCheckRunStatus
from invision_api.services.ai_interview.context import build_interview_context
from invision_api.services.ai_interview.resolution_summary import try_generate_and_persist_resolution_summary
from invision_api.services.ai_interview.data_readiness import get_data_check_overall_status
from invision_api.services.ai_interview.generation import generate_questions_llm
from invision_api.services.ai_interview.prioritize import compute_signal_weight, question_count_from_weight
from invision_api.services.stage_transition_policy import TransitionContext, TransitionName, apply_transition


def _context_to_weight_summary(ctx: dict[str, Any]) -> dict[str, Any]:
    sig = ctx.get("signals") or {}
    rev = ctx.get("review_snapshot") or {}
    contradictions: list[dict[str, Any]] = []
    cf = rev.get("consistency_flags")
    if isinstance(cf, list):
        for item in cf:
            if isinstance(item, dict):
                contradictions.append({"severity": item.get("severity") or "medium"})
            else:
                contradictions.append({"severity": "medium"})
    exp = sig.get("explainability") or []
    low_conc = list(exp)[:8] if isinstance(exp, list) else []
    return {
        "contradictions": contradictions,
        "attention_flags": list(sig.get("attention_flags") or []),
        "authenticity_concerns": list(sig.get("authenticity_concern_signals") or []),
        "manual_review_required": bool(sig.get("manual_review_required")),
        "low_concreteness": low_conc,
    }


def display_question_text(q: dict[str, Any]) -> str:
    return (q.get("commissionEditedText") or q.get("questionText") or "").strip()


def assert_approved_ai_interview_for_internal_transition(db: Session, application_id: UUID) -> None:
    """Raises ValueError when internal transition to interview must not proceed without commission-approved AI set."""
    row = ai_interview_repository.get_question_set_for_application(db, application_id)
    if not row or row.status != "approved":
        raise ValueError(
            "Переход на собеседование доступен только после одобрения набора AI-вопросов в комиссии."
        )
    qs = row.questions or []
    texts = [display_question_text(q) for q in qs if display_question_text(q)]
    if len(texts) < 3 or len(texts) > 5:
        raise ValueError("Требуется утверждённый набор из 3–5 вопросов с непустым текстом.")


def _normalize_sort_orders(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for i, q in enumerate(questions):
        q["sortOrder"] = int(q.get("sortOrder") if q.get("sortOrder") is not None else i)
    questions.sort(key=lambda x: x.get("sortOrder", 0))
    return questions


def _validate_draft_for_approval(questions: list[dict[str, Any]]) -> None:
    texts = [display_question_text(q) for q in questions if display_question_text(q)]
    if len(texts) < 3 or len(texts) > 5:
        raise HTTPException(
            status_code=422,
            detail="Должно быть от 3 до 5 вопросов с непустым текстом.",
        )


def generate_ai_interview_draft(
    db: Session,
    application_id: UUID,
    *,
    force: bool = False,
    actor_user_id: UUID | None = None,
) -> dict[str, Any]:
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if app.current_stage != ApplicationStage.application_review.value:
        raise HTTPException(status_code=409, detail="Генерация доступна только на этапе оценки заявки.")

    existing = ai_interview_repository.get_question_set_for_application(db, application_id)
    if existing and existing.status == "approved":
        if not force:
            raise HTTPException(
                status_code=409,
                detail="Набор уже одобрен. Используйте force=true для новой генерации (черновик перезапишется).",
            )
    if existing and existing.status == "draft" and not force:
        raise HTTPException(
            status_code=409,
            detail="Черновик уже есть. Сохраните правки или вызовите генерацию с force=true (правки будут перезаписаны).",
        )

    settings = get_settings()
    overall = get_data_check_overall_status(db, application_id)
    data_ready = overall == DataCheckRunStatus.ready.value
    if settings.ai_interview_require_data_ready and not data_ready:
        raise HTTPException(
            status_code=409,
            detail=f"Обработка данных не готова для генерации (статус: {overall or 'нет данных'}).",
        )

    ctx = build_interview_context(db, application_id)
    w = compute_signal_weight(_context_to_weight_summary(ctx))
    n = question_count_from_weight(w)
    questions, gen_meta = generate_questions_llm(context=ctx, target_count=n, application_id=application_id)
    for q in questions:
        q.pop("_questionTextSanitized", None)
    questions = _normalize_sort_orders(questions)

    meta = {
        "signal_weight": w,
        "question_count": n,
        "context_keys": list(ctx.keys()),
        **gen_meta,
    }
    logger.info(
        "ai_interview generated application_id=%s weight=%s n=%s path=%s degraded=%s",
        application_id,
        w,
        n,
        gen_meta.get("path"),
        gen_meta.get("degraded"),
    )
    row = ai_interview_repository.upsert_draft(
        db,
        application_id=application_id,
        questions=questions,
        generated_from_signals=meta,
    )
    commission_audit.write_event(
        db,
        event_type="ai_interview_generated",
        entity_type="application",
        entity_id=application_id,
        actor_user_id=actor_user_id,
        after={"revision": row.revision, "question_count": len(questions)},
        metadata={"weight": w, "force": force},
    )
    out = _draft_payload(row)
    out["dataProcessingStatus"] = overall
    out["dataProcessingReady"] = data_ready
    return out


def get_draft_for_commission(db: Session, application_id: UUID) -> dict[str, Any]:
    row = ai_interview_repository.get_question_set_for_application(db, application_id)
    if not row:
        raise HTTPException(status_code=404, detail="Черновик AI-собеседования не найден. Сначала сгенерируйте вопросы.")
    return _draft_payload(row)


def _draft_payload(row: Any) -> dict[str, Any]:
    return {
        "applicationId": str(row.application_id),
        "status": row.status,
        "revision": row.revision,
        "questions": row.questions or [],
        "generatedFromSignals": row.generated_from_signals,
        "generatedAt": row.generated_at.isoformat() if row.generated_at else None,
        "approvedAt": row.approved_at.isoformat() if row.approved_at else None,
        "approvedByUserId": str(row.approved_by_user_id) if row.approved_by_user_id else None,
    }


def patch_draft_questions(
    db: Session,
    application_id: UUID,
    *,
    revision: int,
    questions: list[dict[str, Any]],
    actor_user_id: UUID | None = None,
) -> dict[str, Any]:
    row = ai_interview_repository.get_question_set_for_application(db, application_id)
    if not row:
        raise HTTPException(status_code=404, detail="Черновик не найден.")
    if row.status != "draft":
        raise HTTPException(status_code=409, detail="Редактирование возможно только для черновика.")
    if int(row.revision or 1) != int(revision):
        raise HTTPException(status_code=409, detail="Версия черновика устарела. Обновите страницу.")

    normalized = _normalize_sort_orders([dict(q) for q in questions])
    before_map = {
        str(q.get("id") or ""): display_question_text(q) for q in (row.questions or []) if q.get("id")
    }
    after_map = {str(q.get("id") or ""): display_question_text(q) for q in normalized if q.get("id")}
    all_ids = set(before_map) | set(after_map)
    question_ids_text_changed = sorted(
        i for i in all_ids if before_map.get(i, "") != after_map.get(i, "")
    )
    before_hash = _questions_hash(row.questions or [])
    for q in normalized:
        if q.get("commissionEditedText") or (q.get("isEditedByCommission")):
            q["isEditedByCommission"] = True
        if not q.get("generatedBy"):
            q["generatedBy"] = "commission"

    ai_interview_repository.save_questions_draft(db, row, normalized)
    after_hash = _questions_hash(normalized)
    commission_audit.write_event(
        db,
        event_type="ai_interview_draft_updated",
        entity_type="application",
        entity_id=application_id,
        actor_user_id=actor_user_id,
        before={"text_hash": before_hash},
        after={"text_hash": after_hash, "revision": row.revision},
        metadata={"question_ids_text_changed": question_ids_text_changed},
    )
    return _draft_payload(row)


def _questions_hash(questions: list[dict[str, Any]]) -> str:
    blob = json.dumps(
        [display_question_text(q) for q in questions],
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def approve_ai_interview(db: Session, application_id: UUID, *, actor_user_id: UUID) -> dict[str, Any]:
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    # Idempotent: already approved and on interview (safe retries / double-click).
    if app.current_stage == ApplicationStage.interview.value:
        row = ai_interview_repository.get_question_set_for_application(db, application_id)
        if row and row.status == "approved":
            logger.info("ai_interview approve idempotent application_id=%s", application_id)
            return {
                "current_stage": app.current_stage,
                "state": app.state,
                "aiInterview": _draft_payload(row),
                "alreadyApproved": True,
            }
        raise HTTPException(
            status_code=409,
            detail="Неконсистентное состояние: этап собеседования без утверждённого набора вопросов.",
        )

    if app.current_stage != ApplicationStage.application_review.value:
        raise HTTPException(status_code=409, detail="Одобрение доступно только на этапе оценки заявки.")

    row = ai_interview_repository.get_question_set_for_application_for_update(db, application_id)
    if not row or row.status != "draft":
        raise HTTPException(status_code=409, detail="Нет черновика для одобрения. Сгенерируйте вопросы.")

    qs = row.questions or []
    _validate_draft_for_approval(qs)

    before = {"current_stage": app.current_stage, "state": app.state}
    before_hash = _questions_hash(qs)

    # Snapshot first, then transition; single DB transaction rolls back both on failure.
    ai_interview_repository.mark_approved(db, row, approved_by_user_id=actor_user_id)

    apply_transition(
        db,
        app,
        TransitionContext(
            application_id=app.id,
            transition=TransitionName.review_complete,
            actor_user_id=actor_user_id,
            actor_type="committee",
            internal_note="ai_interview_approved",
        ),
    )
    rebuild_projection(db, app.id)

    logger.info(
        "ai_interview approved application_id=%s actor=%s revision=%s",
        application_id,
        actor_user_id,
        row.revision,
    )

    commission_audit.write_event(
        db,
        event_type="ai_interview_approved",
        entity_type="application",
        entity_id=application_id,
        actor_user_id=actor_user_id,
        before={"text_hash": before_hash, "stage": before},
        after={"current_stage": app.current_stage, "state": app.state},
        metadata={},
    )
    commission_audit.write_event(
        db,
        event_type="stage_advanced",
        entity_type="application",
        entity_id=app.id,
        actor_user_id=actor_user_id,
        before=before,
        after={"current_stage": app.current_stage, "state": app.state},
        metadata={"reason_comment": "ai_interview_approve"},
    )
    return {
        "current_stage": app.current_stage,
        "state": app.state,
        "aiInterview": _draft_payload(row),
        "alreadyApproved": False,
    }


def get_approved_questions_for_candidate(db: Session, application_id: UUID) -> list[dict[str, Any]]:
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if app.current_stage != ApplicationStage.interview.value:
        # Not an error: caller may poll before redirect; avoid 404 spam in logs.
        return []

    row = ai_interview_repository.get_question_set_for_application(db, application_id)
    if not row or row.status != "approved":
        raise HTTPException(status_code=404, detail="Вопросы собеседования ещё не утверждены.")

    out: list[dict[str, Any]] = []
    for q in sorted(row.questions or [], key=lambda x: x.get("sortOrder", 0)):
        text = display_question_text(q)
        if not text:
            continue
        out.append(
            {
                "id": str(q.get("id") or ""),
                "sortOrder": int(q.get("sortOrder") or 0),
                "questionText": text,
            }
        )
    return out


def list_candidate_answers_for_application(db: Session, application_id: UUID) -> list[dict[str, Any]]:
    """Saved AI interview answers for the candidate (same gates as get_approved_questions_for_candidate)."""
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if app.current_stage != ApplicationStage.interview.value:
        return []

    row = ai_interview_repository.get_question_set_for_application(db, application_id)
    if not row or row.status != "approved":
        raise HTTPException(status_code=404, detail="Вопросы собеседования ещё не утверждены.")

    rows = ai_interview_repository.list_answers(db, application_id)
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "questionId": r.question_id,
                "text": r.answer_text,
                "updatedAt": r.updated_at.isoformat() if getattr(r, "updated_at", None) else None,
            }
        )
    return out


def save_candidate_answers_stub(
    db: Session,
    application_id: UUID,
    *,
    answers: list[dict[str, Any]],
) -> dict[str, Any]:
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if app.current_stage != ApplicationStage.interview.value:
        raise HTTPException(status_code=409, detail="Ответы принимаются на этапе собеседования.")

    row = ai_interview_repository.get_question_set_for_application(db, application_id)
    if not row or row.status != "approved":
        raise HTTPException(status_code=409, detail="Вопросы ещё не утверждены.")
    if row.candidate_completed_at is not None:
        raise HTTPException(status_code=409, detail="AI-собеседование уже завершено, ответы нельзя изменить.")

    allowed = {str(q.get("id")) for q in (row.questions or []) if q.get("id")}
    saved = 0
    for a in answers:
        qid = str(a.get("questionId") or a.get("question_id") or "")
        text = str(a.get("text") or "").strip()
        if not qid or qid not in allowed:
            raise HTTPException(status_code=422, detail=f"Неизвестный questionId: {qid}")
        if len(text) > 8000:
            raise HTTPException(status_code=422, detail="Текст ответа слишком длинный.")
        ai_interview_repository.upsert_answer(db, application_id=application_id, question_id=qid, answer_text=text)
        saved += 1
    prof = db.get(CandidateProfile, app.candidate_profile_id)
    if prof:
        candidate_activity_service.record_candidate_activity_event(
            db,
            application_id=application_id,
            candidate_user_id=prof.user_id,
            event_type="stage_action_started",
            stage=app.current_stage,
            metadata={"source": "ai_interview_answers", "saved": saved},
        )
    return {"saved": saved}


def complete_candidate_ai_interview(db: Session, application_id: UUID) -> dict[str, Any]:
    """Mark AI clarification interview complete after all approved questions have non-empty answers."""
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if app.current_stage != ApplicationStage.interview.value:
        raise HTTPException(status_code=409, detail="Завершение доступно на этапе собеседования.")

    row = ai_interview_repository.get_question_set_for_application(db, application_id)
    if not row or row.status != "approved":
        raise HTTPException(status_code=409, detail="Вопросы ещё не утверждены.")

    if row.candidate_completed_at is not None:
        logger.info(
            "candidate_ai_interview_complete_idempotent application_id=%s session_id=%s",
            application_id,
            row.id,
        )
        return {
            "applicationId": str(application_id),
            "sessionId": str(row.id),
            "status": "completed",
            "completedAt": row.candidate_completed_at.isoformat(),
            "alreadyCompleted": True,
        }

    ordered_qs = [q for q in sorted(row.questions or [], key=lambda x: x.get("sortOrder", 0)) if display_question_text(q)]
    if not ordered_qs:
        raise HTTPException(status_code=422, detail="Нет утверждённых вопросов.")

    answer_rows = {r.question_id: r for r in ai_interview_repository.list_answers(db, application_id)}
    for q in ordered_qs:
        qid = str(q.get("id") or "")
        if not qid:
            continue
        ar = answer_rows.get(qid)
        if not ar or not str(ar.answer_text or "").strip():
            raise HTTPException(
                status_code=422,
                detail="Не на все вопросы дан ответ. Завершение невозможно.",
            )

    now = datetime.now(tz=UTC)
    row.candidate_completed_at = now
    db.flush()
    rebuild_projection(db, application_id)

    from invision_api.services.interview_preference_window.service import open_preference_window_on_ai_complete

    open_preference_window_on_ai_complete(db, app)
    rebuild_projection(db, application_id)

    prof = db.get(CandidateProfile, app.candidate_profile_id)
    actor_uid = prof.user_id if prof else None
    audit_log_service.write_audit(
        db,
        entity_type="application",
        entity_id=application_id,
        action="candidate_ai_interview_completed",
        actor_user_id=actor_uid,
        after_data={"session_id": str(row.id), "completed_at": now.isoformat()},
    )
    logger.info(
        "candidate_ai_interview_completed application_id=%s session_id=%s",
        application_id,
        row.id,
    )
    if actor_uid is not None:
        candidate_activity_service.record_candidate_activity_event(
            db,
            application_id=application_id,
            candidate_user_id=actor_uid,
            event_type="ai_interview_completed",
            occurred_at=now,
            stage=app.current_stage,
        )

    try_generate_and_persist_resolution_summary(db, application_id, row)

    return {
        "applicationId": str(application_id),
        "sessionId": str(row.id),
        "status": "completed",
        "completedAt": now.isoformat(),
        "alreadyCompleted": False,
    }


def get_candidate_ai_interview_status(db: Session, application_id: UUID) -> dict[str, Any]:
    from invision_api.services.commission_interview_scheduling.service import interview_session_to_api_dict
    from invision_api.services.interview_preference_window.service import (
        build_preference_window_payload_for_candidate,
        get_commission_interview_session,
    )

    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    row = ai_interview_repository.get_question_set_for_application(db, application_id)
    ai_done = bool(row and row.candidate_completed_at)
    prefs_done = bool(app.interview_preferences_submitted_at)
    n_approved = 0
    n_answered = 0
    if row and row.status == "approved":
        for q in row.questions or []:
            if display_question_text(q):
                n_approved += 1
        if n_approved:
            ans = ai_interview_repository.list_answers(db, application_id)
            answered_ids = {r.question_id for r in ans if str(r.answer_text or "").strip()}
            for q in row.questions or []:
                qid = str(q.get("id") or "")
                if qid and display_question_text(q) and qid in answered_ids:
                    n_answered += 1

    pref_win = build_preference_window_payload_for_candidate(db, app)
    sched_sess = get_commission_interview_session(db, application_id)
    scheduled_interview = (
        interview_session_to_api_dict(sched_sess)
        if sched_sess and sched_sess.scheduled_at
        else None
    )

    return {
        "aiInterviewCompleted": ai_done,
        "preferencesSubmitted": prefs_done,
        "approvedQuestionCount": n_approved,
        "answeredQuestionCount": n_answered,
        "preferenceWindow": pref_win,
        "scheduledInterview": scheduled_interview,
    }


def build_commission_ai_interview_session_view(db: Session, application_id: UUID) -> dict[str, Any]:
    """Read-only Q/A + preferred slots + preference window + commission schedule for commission UI."""
    from invision_api.services.commission_interview_scheduling.service import interview_session_to_api_dict
    from invision_api.services.interview_preferences.service import SLOT_LABEL_BY_CODE
    from invision_api.services.interview_preference_window.service import (
        ensure_preference_window_expired_for_application,
        get_commission_interview_session,
    )

    app_row = admissions_repository.get_application_by_id(db, application_id)
    if not app_row:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    ensure_preference_window_expired_for_application(db, application_id)
    db.refresh(app_row)

    row = ai_interview_repository.get_question_set_for_application(db, application_id)
    completed_at = row.candidate_completed_at.isoformat() if row and row.candidate_completed_at else None

    items: list[dict[str, Any]] = []
    if row and row.status == "approved":
        answer_map = {r.question_id: r.answer_text for r in ai_interview_repository.list_answers(db, application_id)}
        for order, q in enumerate(sorted(row.questions or [], key=lambda x: x.get("sortOrder", 0)), start=1):
            qtext = display_question_text(q)
            if not qtext:
                continue
            qid = str(q.get("id") or "")
            items.append(
                {
                    "questionId": qid,
                    "questionText": qtext,
                    "answerText": str(answer_map.get(qid, "") or ""),
                    "order": order,
                }
            )

    from invision_api.models.commission import InterviewSlotBooking

    slot_rows = list(
        db.scalars(
            select(InterviewSlotBooking)
            .where(InterviewSlotBooking.application_id == application_id)
            .order_by(InterviewSlotBooking.sort_order, InterviewSlotBooking.slot_date)
        ).all()
    )
    preferred_slots = [
        {
            "date": r.slot_date.isoformat(),
            "timeRangeCode": r.time_range_code,
            "timeRange": SLOT_LABEL_BY_CODE.get(r.time_range_code, r.time_range_code),
        }
        for r in slot_rows
    ]

    resolution_summary = row.resolution_summary if row else None
    resolution_error = row.resolution_summary_error if row else None

    wst = app_row.interview_preference_window_status
    wopen = app_row.interview_preference_window_opened_at
    wexp = app_row.interview_preference_window_expires_at
    remaining_sec: int | None = None
    if wst == InterviewPreferenceWindowStatus.awaiting_candidate_preferences.value and wexp is not None:
        remaining_sec = max(0, int((wexp - datetime.now(tz=UTC)).total_seconds()))

    submitted_at_iso = (
        app_row.interview_preferences_submitted_at.isoformat()
        if app_row.interview_preferences_submitted_at
        else None
    )

    commission_sess = get_commission_interview_session(db, application_id)
    scheduled_interview = (
        interview_session_to_api_dict(commission_sess)
        if commission_sess and commission_sess.scheduled_at
        else None
    )

    return {
        "applicationId": str(application_id),
        "candidateId": str(app_row.candidate_profile_id),
        "sessionId": str(row.id) if row else None,
        "interviewCompletedAt": completed_at,
        "questionsAndAnswers": items,
        "preferredSlots": preferred_slots,
        "candidatePreferencePanel": {
            "preferredSlots": preferred_slots,
            "preferencesSubmittedAt": submitted_at_iso,
            "windowStatus": wst,
            "windowOpenedAt": wopen.isoformat() if wopen else None,
            "windowExpiresAt": wexp.isoformat() if wexp else None,
            "remainingSeconds": remaining_sec,
        },
        "commissionSchedule": {
            "scheduledInterview": scheduled_interview,
        },
        "resolutionSummary": resolution_summary,
        "resolutionSummaryError": resolution_error,
    }
