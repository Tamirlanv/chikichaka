from __future__ import annotations

import base64
import csv
import io
import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from invision_api.commission.application import audit as commission_audit
from invision_api.commission.application import kanban_border_hints
from invision_api.commission.application.ai_pipeline_service import CommissionAIPipelineResult, run_commission_ai_pipeline
from invision_api.commission.domain.mapping import (
    application_to_commission_column,
    derive_visual_status,
)
from invision_api.commission.domain.types import (
    AIPlaceholderSummary,
    AIRecommendation,
    FinalDecision,
    InternalRecommendation,
    KanbanCard,
    ReviewerRubric,
    RubricScore,
    StageStatus,
)
from invision_api.models.application import AIReviewMetadata, Application, InterviewSession
from invision_api.models.commission import ApplicationComment, ApplicationCommissionProjection, ExportJob
from invision_api.models.enums import ApplicationStage
from invision_api.repositories import admissions_repository, commission_repository
from invision_api.repositories.application_repository import create_initial_application
from invision_api.commission.application.stage_transition_guard import (
    http_detail_from_resolution,
    resolve_kanban_advance,
)
from invision_api.services.stage_transition_policy import TransitionContext, TransitionName, apply_transition
from invision_api.services.stages import decision_service
from invision_api.services.stages.application_review_service import transition_to_interview

logger = logging.getLogger(__name__)


def _load_application(db: Session, application_id: UUID) -> Application:
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    return app


def _pick_display_interview_session(sessions: list[InterviewSession]) -> InterviewSession | None:
    if not sessions:
        return None
    scheduled = [s for s in sessions if s.scheduled_at]
    if scheduled:
        return max(scheduled, key=lambda s: s.scheduled_at)
    return max(sessions, key=lambda s: s.created_at)


def _education_track_from_app(app: Application) -> str | None:
    for ss in app.section_states or []:
        if ss.section_key == "education" and isinstance(ss.payload, dict):
            entries = ss.payload.get("entries") or []
            if entries and isinstance(entries[0], dict):
                e0 = entries[0]
                fos = e0.get("field_of_study") or e0.get("degree_or_program")
                if isinstance(fos, str) and fos.strip():
                    return fos.strip()
    return None


def _enrich_kanban_border_hints(db: Session, cards: list[KanbanCard]) -> list[KanbanCard]:
    """Fill interview schedule + rubric/stage-one hints for main board cards."""
    if not cards:
        return cards
    app_ids = [c.application_id for c in cards]
    rows = db.scalars(select(InterviewSession).where(InterviewSession.application_id.in_(app_ids))).all()
    by_app: dict[UUID, list[InterviewSession]] = {}
    for r in rows:
        by_app.setdefault(r.application_id, []).append(r)

    out: list[KanbanCard] = []
    for c in cards:
        sess_list = by_app.get(c.application_id, [])
        pick = _pick_display_interview_session(sess_list)
        sched_iso = pick.scheduled_at.isoformat() if pick and pick.scheduled_at else None
        review_total = kanban_border_hints.application_review_total_score(db, c.application_id)
        rubric_ok = review_total is not None
        stage_one = kanban_border_hints.stage_one_data_ready(db, c.application_id, has_ai_summary=c.has_ai_summary)
        dc_status = (
            kanban_border_hints.latest_data_check_run_status(db, c.application_id)
            if c.stage_column == "data_check"
            else c.data_check_run_status
        )
        out.append(
            replace(
                c,
                interview_scheduled_at_iso=sched_iso or c.interview_scheduled_at_iso,
                rubric_three_sections_complete=rubric_ok,
                application_review_total_score=review_total,
                stage_one_data_ready=stage_one,
                data_check_run_status=dc_status,
            )
        )
    return out


def _enrich_interview_kanban_cards(db: Session, cards: list[KanbanCard]) -> list[KanbanCard]:
    if not cards:
        return cards
    app_ids = [c.application_id for c in cards]
    rows = db.scalars(select(InterviewSession).where(InterviewSession.application_id.in_(app_ids))).all()
    by_app: dict[UUID, list[InterviewSession]] = {}
    for r in rows:
        by_app.setdefault(r.application_id, []).append(r)

    apps = db.scalars(
        select(Application).options(selectinload(Application.section_states)).where(Application.id.in_(app_ids))
    ).unique().all()
    app_by_id = {a.id: a for a in apps}

    out: list[KanbanCard] = []
    for c in cards:
        sess_list = by_app.get(c.application_id, [])
        pick = _pick_display_interview_session(sess_list)
        sched_iso = pick.scheduled_at.isoformat() if pick and pick.scheduled_at else None
        sched_by = pick.scheduled_by_user_id if pick else None
        app = app_by_id.get(c.application_id)
        track = _education_track_from_app(app) if app else None
        out.append(
            KanbanCard(
                application_id=c.application_id,
                candidate_full_name=c.candidate_full_name,
                program=c.program,
                age=c.age,
                city=c.city,
                phone=c.phone,
                submitted_at_iso=c.submitted_at_iso,
                updated_at_iso=c.updated_at_iso,
                stage_column=c.stage_column,
                stage_status=c.stage_status,
                attention_flag_manual=c.attention_flag_manual,
                final_decision=c.final_decision,
                visual_status=c.visual_status,
                visual_reason=c.visual_reason,
                comment_count=c.comment_count,
                has_ai_summary=c.has_ai_summary,
                ai_recommendation=c.ai_recommendation,
                interview_scheduled_at_iso=sched_iso,
                interview_scheduled_by_user_id=sched_by,
                education_track=track,
                ai_interview_completed_at_iso=c.ai_interview_completed_at_iso,
                rubric_three_sections_complete=c.rubric_three_sections_complete,
                application_review_total_score=c.application_review_total_score,
                stage_one_data_ready=c.stage_one_data_ready,
                data_check_run_status=c.data_check_run_status,
            )
        )
    return out


def _interview_in_scope_mine(card: KanbanCard, user_id: UUID) -> bool:
    if not card.interview_scheduled_at_iso:
        return False
    return card.interview_scheduled_by_user_id == user_id


def list_applications(
    db: Session,
    *,
    stage: str | None,
    stage_status: str | None,
    attention_only: bool,
    program: str | None,
    search: str | None,
    limit: int,
    offset: int,
    scope: str | None = None,
    current_user_id: UUID | None = None,
    interview_kanban_only: bool = False,
) -> list[KanbanCard]:
    rows = commission_repository.list_projections(
        db,
        stage=stage,
        stage_status=stage_status,
        attention_only=attention_only,
        program=program,
        search=search,
        interview_kanban_only=interview_kanban_only,
        limit=limit,
        offset=offset,
    )
    if not rows:
        apps = list(db.scalars(select(Application).order_by(Application.updated_at.desc()).limit(500)).all())
        for app in apps:
            if app.locked_after_submit or app.submitted_at is not None:
                commission_repository.upsert_projection_for_application(db, app)
        db.flush()
        rows = commission_repository.list_projections(
            db,
            stage=stage,
            stage_status=stage_status,
            attention_only=attention_only,
            program=program,
            search=search,
            interview_kanban_only=interview_kanban_only,
            limit=limit,
            offset=offset,
        )
    out: list[KanbanCard] = []
    for r in rows:
        comment_count = (
            db.scalar(select(func.count(ApplicationComment.id)).where(ApplicationComment.application_id == r.application_id)) or 0
        )
        v = derive_visual_status(stage_status=r.current_stage_status, final_decision_status=r.final_decision)
        out.append(
            KanbanCard(
                application_id=r.application_id,
                candidate_full_name=r.candidate_full_name,
                program=r.program,
                age=r.age,
                city=r.city,
                phone=r.phone,
                submitted_at_iso=r.submitted_at.isoformat() if r.submitted_at else None,
                updated_at_iso=r.updated_at.isoformat(),
                stage_column=application_to_commission_column(r.current_stage),
                stage_status=StageStatus(r.current_stage_status) if r.current_stage_status else None,
                attention_flag_manual=r.attention_flag_manual,
                final_decision=FinalDecision(r.final_decision) if r.final_decision in {x.value for x in FinalDecision} else None,
                visual_status=v.kind,  # type: ignore[arg-type]
                visual_reason=v.reason,
                comment_count=comment_count,
                has_ai_summary=r.has_ai_summary,
                ai_recommendation=AIRecommendation(r.ai_recommendation)
                if r.ai_recommendation in {x.value for x in AIRecommendation}
                else None,
                ai_interview_completed_at_iso=r.ai_interview_completed_at.isoformat()
                if r.ai_interview_completed_at
                else None,
            )
        )
    out = _enrich_kanban_border_hints(db, out)
    if stage == ApplicationStage.interview.value:
        out = _enrich_interview_kanban_cards(db, out)
        if scope == "mine" and current_user_id is not None:
            out = [c for c in out if _interview_in_scope_mine(c, current_user_id)]
    return out


def list_archived_applications(
    db: Session,
    *,
    program: str | None,
    search: str | None,
    limit: int,
    offset: int,
) -> list[KanbanCard]:
    rows = commission_repository.list_archived_projections(
        db,
        program=program,
        search=search,
        limit=limit,
        offset=offset,
    )
    out: list[KanbanCard] = []
    for r in rows:
        comment_count = (
            db.scalar(select(func.count(ApplicationComment.id)).where(ApplicationComment.application_id == r.application_id)) or 0
        )
        v = derive_visual_status(stage_status=r.current_stage_status, final_decision_status=r.final_decision)
        out.append(
            KanbanCard(
                application_id=r.application_id,
                candidate_full_name=r.candidate_full_name,
                program=r.program,
                age=r.age,
                city=r.city,
                phone=r.phone,
                submitted_at_iso=r.submitted_at.isoformat() if r.submitted_at else None,
                updated_at_iso=r.updated_at.isoformat(),
                stage_column=application_to_commission_column(r.current_stage),
                stage_status=StageStatus(r.current_stage_status) if r.current_stage_status else None,
                attention_flag_manual=r.attention_flag_manual,
                final_decision=FinalDecision(r.final_decision) if r.final_decision in {x.value for x in FinalDecision} else None,
                visual_status=v.kind,  # type: ignore[arg-type]
                visual_reason=v.reason,
                comment_count=comment_count,
                has_ai_summary=r.has_ai_summary,
                ai_recommendation=AIRecommendation(r.ai_recommendation)
                if r.ai_recommendation in {x.value for x in AIRecommendation}
                else None,
                ai_interview_completed_at_iso=r.ai_interview_completed_at.isoformat()
                if r.ai_interview_completed_at
                else None,
            )
        )
    return _enrich_kanban_border_hints(db, out)


def archive_application_by_commission(
    db: Session,
    *,
    application_id: UUID,
    actor_user_id: UUID | None,
    reason: str | None = None,
) -> dict[str, UUID]:
    """Mark application archived (history), create a fresh active application for the candidate."""
    app = _load_application(db, application_id)
    if app.is_archived:
        raise HTTPException(status_code=409, detail="Заявка уже архивирована")
    old_id = app.id
    app.is_archived = True
    db.flush()
    commission_repository.upsert_projection_for_application(db, app)
    new_app = create_initial_application(db, app.candidate_profile_id)
    db.flush()
    commission_repository.upsert_projection_for_application(db, new_app)
    commission_audit.write_event(
        db,
        event_type="application_archived_by_commission",
        entity_type="application",
        entity_id=old_id,
        actor_user_id=actor_user_id,
        before={"is_archived": False},
        after={"is_archived": True},
        metadata={
            "new_application_id": str(new_app.id),
            "candidate_profile_id": str(app.candidate_profile_id),
            "reason": (reason or "").strip() or None,
        },
    )
    return {"archived_application_id": old_id, "new_application_id": new_app.id}


def rebuild_projection(db: Session, application_id: UUID) -> ApplicationCommissionProjection:
    app = _load_application(db, application_id)
    row = commission_repository.upsert_projection_for_application(db, app)
    db.flush()
    return row


def get_application_details(db: Session, application_id: UUID) -> dict:
    app = _load_application(db, application_id)
    row = commission_repository.upsert_projection_for_application(db, app)
    sections = {s.section_key: s.payload for s in app.section_states}
    comments = commission_repository.list_comments(db, application_id=application_id, limit=50)
    tags = commission_repository.list_application_tags(db, application_id)
    rubric_rows = commission_repository.list_rubric_scores(db, application_id)
    rec_rows = commission_repository.list_internal_recommendations(db, application_id)
    ai = get_ai_summary(db, application_id=application_id)
    activity = list_audit(db, application_id=application_id, limit=30)
    validation_report = commission_repository.get_latest_validation_report(db, application_id)

    personal = sections.get("personal") if isinstance(sections.get("personal"), dict) else {}
    contact = sections.get("contact") if isinstance(sections.get("contact"), dict) else {}
    education = sections.get("education") if isinstance(sections.get("education"), dict) else {}
    motivation = sections.get("motivation_letter") if isinstance(sections.get("motivation_letter"), dict) else {}
    growth = sections.get("growth_journey") if isinstance(sections.get("growth_journey"), dict) else {}
    achievements = sections.get("achievements_activities") if isinstance(sections.get("achievements_activities"), dict) else {}
    internal_test = sections.get("internal_test") if isinstance(sections.get("internal_test"), dict) else {}

    answers = growth.get("answers") if isinstance(growth, dict) else None
    path_answers: list[dict[str, Any]] = []
    if isinstance(answers, dict):
        labels = {
            "q1": "Опыт, который повлиял на путь",
            "q2": "Значимая трудность",
            "q3": "Инициатива и ответственность",
            "q4": "Рост и изменения",
            "q5": "Почему именно inVision U",
        }
        for qid in ("q1", "q2", "q3", "q4", "q5"):
            a = answers.get(qid)
            if isinstance(a, dict):
                path_answers.append(
                    {
                        "questionKey": qid,
                        "questionTitle": labels.get(qid, qid),
                        "text": str(a.get("text") or ""),
                    }
                )

    stage_status = row.current_stage_status or "new"
    current_stage = application_to_commission_column(app.current_stage)
    available_actions: list[str] = []
    if not app.is_archived:
        if current_stage != "result":
            available_actions.append("set_stage_status")
        if app.current_stage in ("initial_screening", "interview", "committee_review"):
            available_actions.append("advance_stage")
        if app.current_stage in ("committee_review", "decision"):
            available_actions.append("set_final_decision")
    return {
        "application_id": str(app.id),
        "is_archived": app.is_archived,
        "read_only": app.is_archived,
        "current_stage": app.current_stage,
        "state": app.state,
        "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
        "candidate": {
            "full_name": row.candidate_full_name,
            "city": row.city,
            "phone": row.phone,
            "program": row.program,
            "age": row.age,
        },
        "stage": {
            "currentStage": current_stage,
            "currentStageStatus": stage_status,
            "finalDecision": row.final_decision,
            "availableNextActions": available_actions,
        },
        "personalInfo": {
            "basicInfo": personal,
            "contacts": contact,
            "guardians": (personal.get("guardians") if isinstance(personal, dict) else []) or [],
            "address": (contact.get("address") if isinstance(contact, dict) else {}) or {},
            "education": education,
        },
        "test": internal_test or None,
        "motivation": motivation or None,
        "path": {
            "answers": path_answers,
            "summary": ((growth.get("computed") or {}).get("llm_summary") if isinstance(growth, dict) else None),
            "keyThemes": (((growth.get("computed") or {}).get("section_signals") or {}).get("key_themes") if isinstance(growth, dict) else None),
        }
        if path_answers or (isinstance(growth, dict) and growth.get("computed"))
        else None,
        "achievements": achievements or None,
        "aiSummary": {
            "summaryText": ai.summary_text,
            "strengths": ai.strengths,
            "weakPoints": ai.weak_points,
            "leadershipSignals": ai.leadership_signals,
            "missionFitNotes": ai.mission_fit_notes,
            "keyThemes": ai.key_themes,
            "evidenceHighlights": ai.evidence_highlights,
            "possibleFollowUpTopics": ai.possible_follow_up_topics,
            "redFlags": ai.red_flags,
            "recommendation": ai.recommendation.value if ai.recommendation else None,
            "confidenceScore": ai.confidence_score,
            "explainabilityNotes": [ai.explainability_notes] if ai.explainability_notes else [],
            "generatedAt": ai.generated_at_iso,
            "inputHash": ai.input_hash,
            "pipelineVersion": ai.pipeline_version,
            "status": "ready" if ai.status == "ready" else ("failed" if ai.status == "failed" else "not_generated"),
        },
        "review": {
            "rubricScores": [
                {
                    "criterion": r.rubric,
                    "value": r.score,
                    "authorId": str(r.reviewer_user_id),
                    "updatedAt": r.updated_at.isoformat(),
                }
                for r in rubric_rows
            ],
            "internalRecommendations": [
                {
                    "authorId": str(r.reviewer_user_id),
                    "recommendation": r.recommendation,
                    "reasonComment": r.reason_comment,
                    "updatedAt": r.updated_at.isoformat(),
                }
                for r in rec_rows
            ],
            "tags": tags,
        },
        "comments": [
            {
                "id": str(c.id),
                "text": c.body,
                "authorId": str(c.author_user_id) if c.author_user_id else None,
                "createdAt": c.created_at.isoformat() if c.created_at else None,
                "tags": [t.key for t in c.tags] if c.tags else [],
            }
            for c in comments
        ],
        "recentActivity": activity,
        "validationReport": validation_report,
        "sections": sections,
    }


def advance_stage(db: Session, application_id: UUID, actor_user_id: UUID | None, reason_comment: str | None) -> dict:
    app = _load_application(db, application_id)
    resolution = resolve_kanban_advance(db, application_id)
    if not resolution.allowed or resolution.transition is None:
        code = resolution.block_code.value if resolution.block_code else "UNKNOWN"
        logger.info(
            "commission_stage_advance_blocked application_id=%s code=%s",
            application_id,
            code,
        )
        raise HTTPException(status_code=409, detail=http_detail_from_resolution(resolution))
    before = {"current_stage": app.current_stage, "state": app.state}
    transition = resolution.transition
    if transition == TransitionName.review_complete:
        transition_to_interview(db, app, actor_user_id=actor_user_id)
    else:
        apply_transition(
            db,
            app,
            TransitionContext(
                application_id=app.id,
                transition=transition,
                actor_user_id=actor_user_id,
                actor_type="committee",
                internal_note=reason_comment,
            ),
        )
    rebuild_projection(db, app.id)
    commission_audit.write_event(
        db,
        event_type="stage_advanced",
        entity_type="application",
        entity_id=app.id,
        actor_user_id=actor_user_id,
        before=before,
        after={"current_stage": app.current_stage, "state": app.state},
        metadata={"reason_comment": reason_comment},
    )
    return {"current_stage": app.current_stage, "state": app.state}


def set_stage_status(
    db: Session,
    *,
    application_id: UUID,
    status_value: StageStatus,
    actor_user_id: UUID | None,
    reason_comment: str | None,
) -> dict:
    app = _load_application(db, application_id)
    if status_value == StageStatus.needs_attention and not (reason_comment or "").strip():
        raise HTTPException(status_code=422, detail="Комментарий обязателен для needs_attention")
    row = commission_repository.set_stage_status(
        db,
        application_id=application_id,
        stage=app.current_stage,
        status=status_value.value,
        actor_user_id=actor_user_id,
        reason_comment=reason_comment,
    )
    rebuild_projection(db, application_id)
    commission_audit.write_event(
        db,
        event_type="stage_status_changed",
        entity_type="application",
        entity_id=application_id,
        actor_user_id=actor_user_id,
        after={"stage": app.current_stage, "status": row.status},
        metadata={"reason_comment": reason_comment},
    )
    return {"stage": app.current_stage, "status": row.status, "revision": row.revision}


def set_attention(
    db: Session,
    *,
    application_id: UUID,
    value: bool,
    actor_user_id: UUID | None,
    reason_comment: str | None,
) -> dict:
    app = _load_application(db, application_id)
    row = commission_repository.set_attention_flag(db, application_id=application_id, stage=app.current_stage, value=value)
    rebuild_projection(db, application_id)
    commission_audit.write_event(
        db,
        event_type="attention_flag_changed",
        entity_type="application",
        entity_id=application_id,
        actor_user_id=actor_user_id,
        after={"stage": app.current_stage, "attention_flag_manual": value},
        metadata={"reason_comment": reason_comment},
    )
    return {"stage": app.current_stage, "attention_flag_manual": row.attention_flag_manual, "revision": row.revision}


def add_comment(db: Session, *, application_id: UUID, actor_user_id: UUID | None, body: str) -> dict:
    app = _load_application(db, application_id)
    if not body.strip():
        raise HTTPException(status_code=422, detail="Комментарий пуст")
    row = commission_repository.create_comment(db, application_id=app.id, author_user_id=actor_user_id, body=body.strip())
    commission_audit.write_event(
        db,
        event_type="comment_added",
        entity_type="application",
        entity_id=application_id,
        actor_user_id=actor_user_id,
        after={"comment_id": str(row.id)},
    )
    return {"id": str(row.id), "body": row.body, "created_at": row.created_at.isoformat() if row.created_at else None}


def list_comments(db: Session, *, application_id: UUID, limit: int = 100) -> list[dict]:
    _load_application(db, application_id)
    rows = commission_repository.list_comments(db, application_id=application_id, limit=limit)
    return [
        {
            "id": str(r.id),
            "body": r.body,
            "author_user_id": str(r.author_user_id) if r.author_user_id else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def set_tags(
    db: Session,
    *,
    application_id: UUID,
    actor_user_id: UUID | None,
    tag_keys: list[str],
) -> dict:
    _load_application(db, application_id)
    cleaned = commission_repository.set_application_tags(db, application_id=application_id, tag_keys=tag_keys)
    commission_audit.write_event(
        db,
        event_type="tags_updated",
        entity_type="application",
        entity_id=application_id,
        actor_user_id=actor_user_id,
        after={"tags": cleaned},
    )
    return {"tags": cleaned}


def set_rubric_scores(
    db: Session,
    *,
    application_id: UUID,
    reviewer_user_id: UUID,
    scores: dict[ReviewerRubric, RubricScore],
    comment: str | None,
) -> dict:
    _load_application(db, application_id)
    for rubric, score in scores.items():
        commission_repository.upsert_rubric_score(
            db,
            application_id=application_id,
            reviewer_user_id=reviewer_user_id,
            rubric=rubric.value,
            score=score.value,
            comment=comment,
        )
    commission_audit.write_event(
        db,
        event_type="rubric_updated",
        entity_type="application",
        entity_id=application_id,
        actor_user_id=reviewer_user_id,
        after={"scores": {k.value: v.value for k, v in scores.items()}},
    )
    return {"ok": True}


def set_internal_recommendation(
    db: Session,
    *,
    application_id: UUID,
    reviewer_user_id: UUID,
    recommendation: InternalRecommendation,
    reason_comment: str | None,
) -> dict:
    if recommendation == InternalRecommendation.reject and not (reason_comment or "").strip():
        raise HTTPException(status_code=422, detail="Комментарий обязателен для reject")
    row = commission_repository.upsert_internal_recommendation(
        db,
        application_id=application_id,
        reviewer_user_id=reviewer_user_id,
        recommendation=recommendation.value,
        reason_comment=reason_comment,
    )
    commission_audit.write_event(
        db,
        event_type="internal_recommendation_updated",
        entity_type="application",
        entity_id=application_id,
        actor_user_id=reviewer_user_id,
        after={"recommendation": row.recommendation},
    )
    return {"recommendation": row.recommendation, "reason_comment": row.reason_comment}


def set_final_decision(
    db: Session,
    *,
    application_id: UUID,
    actor_user_id: UUID,
    final_decision: FinalDecision,
    reason_comment: str | None,
) -> dict:
    if final_decision in (FinalDecision.reject, FinalDecision.waitlist) and not (reason_comment or "").strip():
        raise HTTPException(status_code=422, detail="Комментарий обязателен для reject/waitlist")
    app = _load_application(db, application_id)
    decision = decision_service.record_final_decision(
        db,
        app,
        actor_user_id=actor_user_id,
        final_decision_status=final_decision.value,
        candidate_message=None,
        internal_note=reason_comment,
        next_steps=None,
    )
    rebuild_projection(db, application_id)
    commission_audit.write_event(
        db,
        event_type="final_decision_set",
        entity_type="application",
        entity_id=application_id,
        actor_user_id=actor_user_id,
        after={"final_decision": final_decision.value},
        metadata={"reason_comment": reason_comment},
    )
    return {"id": str(decision.id), "final_decision": decision.final_decision_status}


def list_audit(db: Session, *, application_id: UUID, limit: int = 200) -> list[dict]:
    from invision_api.models.application import AuditLog

    _load_application(db, application_id)
    rows = list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.entity_type == "application", AuditLog.entity_id == application_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        ).all()
    )
    return [
        {
            "id": str(r.id),
            "event_type": r.action,
            "entity_type": r.entity_type,
            "entity_id": str(r.entity_id),
            "actor_user_id": str(r.actor_user_id) if r.actor_user_id else None,
            "timestamp": r.created_at.isoformat(),
            "previous_value": r.before_data,
            "next_value": r.after_data,
            "metadata": (r.after_data or {}).get("metadata") if isinstance(r.after_data, dict) else None,
        }
        for r in rows
    ]


def list_updates(db: Session, *, cursor: str | None, limit: int = 500) -> dict:
    since: datetime | None = None
    if cursor:
        try:
            since = datetime.fromisoformat(cursor.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=422, detail="Некорректный cursor") from None
    stmt = select(ApplicationCommissionProjection).order_by(ApplicationCommissionProjection.updated_at.asc()).limit(limit)
    if since is not None:
        stmt = stmt.where(ApplicationCommissionProjection.updated_at > since)
    rows = list(db.scalars(stmt).all())
    changed = [str(r.application_id) for r in rows]
    latest_cursor = rows[-1].updated_at.isoformat() if rows else (cursor or datetime.now(tz=UTC).isoformat())
    return {"changedApplicationIds": changed, "latestCursor": latest_cursor}


def board_metrics(
    db: Session,
    *,
    range_value: str,
    search: str | None,
    program: str | None,
) -> dict:
    rows = commission_repository.list_projections(
        db,
        stage=None,
        stage_status=None,
        attention_only=False,
        program=program,
        search=search,
        limit=10000,
        offset=0,
    )
    rows_all_programs = commission_repository.list_projections(
        db,
        stage=None,
        stage_status=None,
        attention_only=False,
        program=None,
        search=search,
        limit=10000,
        offset=0,
    )

    def _program_bucket(program_value: str | None) -> str:
        raw = (program_value or "").strip().lower()
        if not raw:
            return "other"
        if "foundation" in raw:
            return "foundation"
        if "бак" in raw or "bachelor" in raw:
            return "bachelor"
        return "other"

    now = datetime.now(tz=UTC)
    if range_value == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif range_value == "week":
        start = (now.replace(hour=0, minute=0, second=0, microsecond=0)) - timedelta(days=now.weekday())
    elif range_value == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif range_value == "year":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    total = len([r for r in rows if (r.submitted_at and r.submitted_at >= start)])
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today = len([r for r in rows if (r.submitted_at and r.submitted_at >= today_start)])
    in_range_by_program = [r for r in rows_all_programs if (r.submitted_at and r.submitted_at >= start)]
    foundation = len([r for r in in_range_by_program if _program_bucket(r.program) == "foundation"])
    bachelor = len([r for r in in_range_by_program if _program_bucket(r.program) == "bachelor"])
    return {
        "totalApplications": total,
        "todayApplications": today,
        "foundationApplications": foundation,
        "bachelorApplications": bachelor,
    }


def get_ai_summary(db: Session, *, application_id: UUID) -> AIPlaceholderSummary:
    _load_application(db, application_id)
    ai = db.scalars(
        select(AIReviewMetadata).where(AIReviewMetadata.application_id == application_id).order_by(AIReviewMetadata.created_at.desc())
    ).first()
    if not ai:
        return AIPlaceholderSummary(
            application_id=application_id,
            status="pending",
            summary_text=None,
            strengths=[],
            weak_points=[],
            red_flags=[],
            leadership_signals=[],
            recommendation=None,
            confidence_score=None,
            explainability_notes=None,
            generated_at_iso=None,
            source_data_version=None,
            mission_fit_notes=[],
            key_themes=[],
            evidence_highlights=[],
            possible_follow_up_topics=[],
            input_hash=None,
            pipeline_version=None,
        )
    flags = ai.flags or {}
    rec: AIRecommendation | None = None
    rec_raw = flags.get("recommendation")
    if rec_raw in {x.value for x in AIRecommendation}:
        rec = AIRecommendation(rec_raw)
    return AIPlaceholderSummary(
        application_id=application_id,
        status="ready" if ai.summary_text else "pending",
        summary_text=ai.summary_text,
        strengths=list(flags.get("strengths") or []),
        weak_points=list(flags.get("weak_points") or []),
        red_flags=list(flags.get("red_flags") or []),
        leadership_signals=list(flags.get("leadership_signals") or []),
        recommendation=rec,
        confidence_score=flags.get("confidence_score"),
        explainability_notes=(ai.explainability_snapshot or {}).get("notes")
        if isinstance(ai.explainability_snapshot, dict)
        else None,
        generated_at_iso=ai.created_at.isoformat() if ai.created_at else None,
        source_data_version=ai.prompt_version,
        mission_fit_notes=list(flags.get("mission_fit_notes") or []),
        key_themes=list(flags.get("key_themes") or []),
        evidence_highlights=list(flags.get("evidence_highlights") or []),
        possible_follow_up_topics=list(flags.get("possible_follow_up_topics") or []),
        input_hash=flags.get("input_hash") if isinstance(flags.get("input_hash"), str) else None,
        pipeline_version=flags.get("pipeline_version") if isinstance(flags.get("pipeline_version"), str) else None,
    )


def run_ai_summary_for_application(
    db: Session,
    *,
    application_id: UUID,
    actor_user_id: UUID,
    force: bool = False,
) -> CommissionAIPipelineResult:
    """Runs explainable hybrid commission AI pipeline (reviewer/admin only at route layer)."""
    _load_application(db, application_id)
    return run_commission_ai_pipeline(db, application_id=application_id, actor_user_id=actor_user_id, force=force)


def create_export_csv_job(
    db: Session,
    *,
    actor_user_id: UUID | None,
    filter_payload: dict | None,
) -> ExportJob:
    rows = commission_repository.list_projections(
        db,
        stage=filter_payload.get("stage") if filter_payload else None,
        stage_status=filter_payload.get("stageStatus") if filter_payload else None,
        attention_only=bool(filter_payload.get("attentionOnly")) if filter_payload else False,
        program=filter_payload.get("program") if filter_payload else None,
        search=filter_payload.get("search") if filter_payload else None,
        limit=5000,
        offset=0,
    )
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "applicationId",
            "candidateFullName",
            "program",
            "city",
            "phone",
            "currentStage",
            "currentStageStatus",
            "finalDecision",
            "aiRecommendation",
            "submittedAt",
            "updatedAt",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                str(r.application_id),
                r.candidate_full_name,
                r.program or "",
                r.city or "",
                r.phone or "",
                r.current_stage,
                r.current_stage_status or "",
                r.final_decision or "",
                r.ai_recommendation or "",
                r.submitted_at.isoformat() if r.submitted_at else "",
                r.updated_at.isoformat(),
            ]
        )
    csv_bytes = out.getvalue().encode("utf-8")
    encoded = base64.b64encode(csv_bytes).decode("ascii")
    job = commission_repository.create_export_job(
        db,
        created_by_user_id=actor_user_id,
        export_format="csv",
        filter_payload=filter_payload,
        application_ids=[str(r.application_id) for r in rows],
    )
    job.status = "completed"
    job.result_storage_key = f"inline:base64:{encoded}"
    job.completed_at = datetime.now(tz=UTC)
    commission_audit.write_event(
        db,
        event_type="export_created",
        entity_type="export_job",
        entity_id=job.id,
        actor_user_id=actor_user_id,
        after={"format": "csv", "status": "completed"},
    )
    return job
