from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.enums import SectionKey
from invision_api.models.video_validation import VideoValidationResultRow
from invision_api.services.data_check.contracts import UnitExecutionResult
from invision_api.services.data_check.utils import get_validated_section
from invision_api.services.video_processing import run_presentation_pipeline
from invision_api.services.video_processing.constants import MEDIA_STATUS_FAILED, MEDIA_STATUS_READY

logger = logging.getLogger(__name__)


def run_video_validation_processing(db: Session, *, application_id: UUID, candidate_id: UUID) -> UnitExecutionResult:
    _ = candidate_id
    validated = get_validated_section(
        db,
        application_id=application_id,
        section_key=SectionKey.education,
    )
    video_url = ""
    if validated and validated.presentation_video_url:
        video_url = validated.presentation_video_url.strip()

    if not video_url:
        return UnitExecutionResult(
            status="manual_review_required",
            payload={"videoUrl": None},
            warnings=[],
            explainability=["Не указан URL видеопрезентации."],
            manual_review_required=True,
        )

    try:
        outcome = run_presentation_pipeline(video_url)
    except Exception:
        logger.exception("video pipeline crashed application_id=%s", application_id)
        row = VideoValidationResultRow(
            application_id=application_id,
            video_url=video_url,
            normalized_url=video_url,
            access_status="unreachable",
            media_status=MEDIA_STATUS_FAILED,
            errors=["Внутренняя ошибка обработки видео."],
            manual_review_required=True,
            summary_text=None,
        )
        db.add(row)
        db.flush()
        return UnitExecutionResult(
            status="failed",
            payload={"resultId": str(row.id), "videoUrl": video_url},
            errors=["Внутренняя ошибка обработки видео."],
            explainability=["Исключение при выполнении пайплайна видео."],
            manual_review_required=True,
        )

    ok = outcome.media_status == MEDIA_STATUS_READY and not outcome.errors
    manual = not ok

    analyzed = outcome.frames_extracted_success
    row = VideoValidationResultRow(
        application_id=application_id,
        video_url=video_url,
        normalized_url=video_url,
        access_status="reachable" if outcome.media_status != MEDIA_STATUS_FAILED else "unreachable",
        media_status=outcome.media_status,
        duration_sec=outcome.duration_sec,
        width=outcome.width,
        height=outcome.height,
        has_video_track=outcome.has_video_track,
        has_audio_track=outcome.has_audio_track,
        total_frames_analyzed=analyzed,
        face_detected_frames_count=outcome.face_detected_frames_count,
        face_coverage_ratio=(outcome.face_detected_frames_count / analyzed) if analyzed else 0.0,
        sampled_timestamps_sec=outcome.sampled_timestamps_sec,
        has_speech=outcome.has_speech,
        speech_segment_count=1 if outcome.has_speech else 0,
        transcript_preview=outcome.raw_transcript or None,
        transcript_confidence=outcome.transcript_confidence,
        likely_face_visible=outcome.candidate_visible,
        likely_speech_audible=outcome.has_speech,
        likely_presentation_valid=ok,
        manual_review_required=manual,
        explainability=["Видеопрезентация обработана."],
        warnings=outcome.warnings,
        errors=list(outcome.errors),
        confidence=0.85 if ok else 0.35,
        summary_text=outcome.commission_summary,
    )
    db.add(row)
    db.flush()

    return UnitExecutionResult(
        status="completed" if ok else "manual_review_required",
        payload={
            "resultId": str(row.id),
            "videoUrl": video_url,
            "mediaStatus": row.media_status,
            "durationSec": row.duration_sec,
        },
        warnings=outcome.warnings,
        errors=list(outcome.errors),
        explainability=row.explainability or [],
        manual_review_required=manual,
    )
