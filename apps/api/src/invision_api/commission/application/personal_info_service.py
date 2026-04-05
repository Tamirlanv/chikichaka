from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.commission.application import service as commission_service
from invision_api.commission.application.personal_info_mapper import build_personal_info_view
from invision_api.commission.application.sidebar_service import compute_commission_document_borders
from invision_api.commission.application.personal_info_validators import (
    load_submitted_application_or_404,
    resolve_commission_actions,
)
from invision_api.models.enums import DataCheckRunStatus, DataCheckUnitStatus, DataCheckUnitType
from invision_api.models.user import User
from invision_api.core.config import get_settings
from invision_api.repositories import (
    ai_interview_repository,
    commission_repository,
    data_check_repository,
    document_repository,
    internal_test_repository,
    video_validation_repository,
)
from invision_api.models.data_check_unit_result import DataCheckUnitResult
from invision_api.services.ai_interview.data_readiness import is_data_processing_ready
from invision_api.services.ai_interview.service import display_question_text
from invision_api.services.application_service import collect_referenced_document_ids
from invision_api.services.data_check.status_service import (
    TERMINAL_UNIT_STATUSES,
    UNIT_POLICIES,
    build_commission_human_issues,
    compute_run_status,
)
from invision_api.services.personality_profile_service import build_personality_profile_snapshot


def _to_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value).strip())
    except (TypeError, ValueError):
        return None


def _certificate_validation_unit(db: Session, application_id: UUID) -> DataCheckUnitResult | None:
    run = data_check_repository.resolve_preferred_run_for_application(db, application_id)
    if not run:
        return None
    results = data_check_repository.list_unit_results_for_run(db, run.id)
    for r in results:
        if r.unit_type == DataCheckUnitType.certificate_validation.value:
            return r
    return None


def _build_processing_status(db: Session, application_id: UUID) -> dict[str, Any] | None:
    run = data_check_repository.resolve_preferred_run_for_application(db, application_id)
    if not run:
        return None
    checks = data_check_repository.list_checks_for_run(db, run.id)
    if not checks:
        return None

    status_map: dict[DataCheckUnitType, str] = {}
    for c in checks:
        try:
            status_map[DataCheckUnitType(c.check_type)] = c.status
        except ValueError:
            continue

    canonical: dict[DataCheckUnitType, str] = {}
    for unit in UNIT_POLICIES:
        canonical[unit] = status_map.get(unit, DataCheckUnitStatus.pending.value)

    run_computed = compute_run_status(canonical)
    completed = sum(1 for s in canonical.values() if s in TERMINAL_UNIT_STATUSES)
    warnings: list[str] = []
    errors: list[str] = []
    if run_computed.status in {DataCheckRunStatus.partial.value, DataCheckRunStatus.failed.value}:
        warnings, errors = build_commission_human_issues(canonical)

    return {
        "overall": run_computed.status,
        "completedCount": completed,
        "totalCount": len(UNIT_POLICIES),
        "units": {unit.value: st for unit, st in canonical.items()},
        "manualReviewRequired": run_computed.manual_review_required,
        "warnings": warnings,
        "errors": errors,
    }


def get_commission_application_personal_info(db: Session, *, application_id: UUID, actor: User) -> dict[str, Any]:
    app = load_submitted_application_or_404(db, application_id)

    projection = commission_repository.upsert_projection_for_application(db, app)
    sections = {s.section_key: s.payload for s in app.section_states}
    stage_status = projection.current_stage_status or "new"

    referenced_document_ids = collect_referenced_document_ids(app)
    all_documents = document_repository.list_documents_for_application(db, app.id)
    documents = [d for d in all_documents if d.id in referenced_document_ids]

    ai_summary = commission_service.get_ai_summary(db, application_id=application_id)
    personality_profile: dict[str, Any] | None = None
    try:
        personality_profile = build_personality_profile_snapshot(db, application_id=application_id, lang="ru")
    except Exception:
        personality_profile = None

    processing_status = _build_processing_status(db, application_id)

    video_row = video_validation_repository.get_latest_for_application(db, application_id)

    education = sections.get("education") if isinstance(sections.get("education"), dict) else {}
    cert_unit = _certificate_validation_unit(db, application_id)
    document_borders = compute_commission_document_borders(
        cert_unit,
        english_document_id=_to_uuid(education.get("english_document_id")),
        certificate_document_id=_to_uuid(education.get("certificate_document_id")),
        additional_document_id=_to_uuid(education.get("additional_document_id")),
    )

    comments = commission_repository.list_comments_with_author(db, application_id=application_id, limit=50)

    qs = ai_interview_repository.get_question_set_for_application(db, application_id)
    n_valid = 0
    if qs and qs.questions:
        n_valid = sum(1 for q in qs.questions if display_question_text(q))
    on_review = app.current_stage == "application_review"
    can_move_from_orange_stage_one = bool(
        app.current_stage == "initial_screening"
        and processing_status
        and processing_status.get("overall") in {DataCheckRunStatus.partial.value, DataCheckRunStatus.failed.value}
    )
    can_advance_stage = can_move_from_orange_stage_one or app.current_stage in (
        "application_review",
        "interview",
        "committee_review",
    )
    settings = get_settings()
    data_ok_for_generate = not settings.ai_interview_require_data_ready or is_data_processing_ready(db, application_id)
    has_final_decision = bool(projection.final_decision)
    is_read_only = bool(app.is_archived or has_final_decision)
    if app.is_archived:
        read_only_reason = "Заявка в архиве: доступен только просмотр."
    elif has_final_decision:
        read_only_reason = "По заявке уже принято финальное решение: доступен только просмотр."
    else:
        read_only_reason = None

    if is_read_only:
        actions = {
            "canComment": False,
            "canMoveForward": False,
            "canApproveAiInterview": False,
            "canGenerateAiInterview": False,
        }
    else:
        actions = resolve_commission_actions(
            db,
            actor,
            can_advance_stage=can_advance_stage,
            can_approve_ai_interview=bool(on_review and qs and qs.status == "draft" and 3 <= n_valid <= 5),
            can_generate_ai_interview=bool(on_review and data_ok_for_generate),
        )

    return build_personal_info_view(
        app=app,
        projection=projection,
        sections=sections,
        stage_status=stage_status,
        ai_summary=ai_summary,
        personality_profile=personality_profile,
        comments=comments,
        documents=documents,
        actions=actions,
        processing_status=processing_status,
        video_row=video_row,
        is_archived=app.is_archived,
        is_read_only=is_read_only,
        read_only_reason=read_only_reason,
        document_borders=document_borders,
    )


def get_commission_application_test_info(db: Session, *, application_id: UUID) -> dict[str, Any]:
    app = load_submitted_application_or_404(db, application_id)

    questions = internal_test_repository.list_active_questions(db)
    answers = internal_test_repository.list_answers_for_application(db, application_id)
    answer_map: dict[str, Any] = {}
    for a in answers:
        answer_map[str(a.question_id)] = a

    personality_profile: dict[str, Any] | None = None
    try:
        personality_profile = build_personality_profile_snapshot(db, application_id=application_id, lang="ru")
    except Exception:
        personality_profile = None

    question_list: list[dict[str, Any]] = []
    for idx, q in enumerate(questions, start=1):
        answer = answer_map.get(str(q.id))
        selected_text: str | None = None
        if answer and answer.selected_options:
            key = str(answer.selected_options[0]).upper()
            opts = q.options or []
            for opt in opts:
                if isinstance(opt, dict) and str(opt.get("key", "")).upper() == key:
                    selected_text = opt.get("text") or opt.get("label") or key
                    break
            if selected_text is None:
                selected_text = key
        elif answer and answer.text_answer:
            selected_text = answer.text_answer
        question_list.append({
            "index": idx,
            "questionId": str(q.id),
            "prompt": q.prompt,
            "selectedAnswer": selected_text,
        })

    ai_about: str | None = None
    ai_weak_points: list[str] = []
    ai_summary_row = commission_service.get_ai_summary(db, application_id=application_id)
    if ai_summary_row:
        ai_about = getattr(ai_summary_row, "summary_text", None)
        ai_weak_points = getattr(ai_summary_row, "weak_points", None) or []

    profile_data: dict[str, Any] | None = None
    if personality_profile:
        profile_data = {
            "profileType": personality_profile.get("profileType"),
            "profileTitle": personality_profile.get("profileTitle"),
            "summary": personality_profile.get("summary"),
            "rawScores": personality_profile.get("rawScores"),
            "ranking": personality_profile.get("ranking"),
            "dominantTrait": personality_profile.get("dominantTrait"),
            "secondaryTrait": personality_profile.get("secondaryTrait"),
            "weakestTrait": personality_profile.get("weakestTrait"),
            "flags": personality_profile.get("flags"),
            "meta": personality_profile.get("meta"),
        }

    return {
        "personalityProfile": profile_data,
        "testLang": "RU",
        "questions": question_list,
        "aiSummary": {
            "aboutCandidate": ai_about,
            "weakPoints": ai_weak_points,
        } if ai_about or ai_weak_points else None,
    }


def create_commission_comment(
    db: Session,
    *,
    application_id: UUID,
    actor_user_id: UUID | None,
    text: str,
) -> dict[str, Any]:
    load_submitted_application_or_404(db, application_id)
    return commission_service.add_comment(db, application_id=application_id, actor_user_id=actor_user_id, body=text)


def move_application_to_next_stage(
    db: Session,
    *,
    application_id: UUID,
    actor_user_id: UUID | None,
    reason_comment: str | None,
) -> dict[str, Any]:
    load_submitted_application_or_404(db, application_id)
    return commission_service.advance_stage(
        db,
        application_id=application_id,
        actor_user_id=actor_user_id,
        reason_comment=reason_comment,
    )
