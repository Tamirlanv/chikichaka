from __future__ import annotations

from sqlalchemy.orm import Session

from invision_api.repositories import link_validation_repository
from invision_api.services.link_validation.availability import determine_availability
from invision_api.services.link_validation.classifier import classify_url
from invision_api.services.link_validation.cloud_hints import cloud_access_hints
from invision_api.services.link_validation.config import LinkValidationConfig
from invision_api.services.link_validation.http_client import HttpProbeClient
from invision_api.services.link_validation.normalizer import normalize_url
from invision_api.services.link_validation.presentation_video import evaluate_presentation_video, video_result_for_invalid_url
from invision_api.services.link_validation.types import LinkValidationRequest, LinkValidationResult, VideoLinkValidationResult
from invision_api.services.link_validation.validator import validate_url_format


def _confidence_score(*, is_valid: bool, reachable: bool, warnings: list[str], errors: list[str]) -> float:
    if not is_valid:
        return 0.0
    score = 0.5
    if reachable:
        score += 0.4
    score -= min(0.3, 0.05 * len(warnings))
    score -= min(0.4, 0.1 * len(errors))
    return round(max(0.0, min(1.0, score)), 2)


def run_candidate_link_pipeline(
    url: str,
    config: LinkValidationConfig | None = None,
    probe_client: HttpProbeClient | None = None,
) -> tuple[LinkValidationResult, VideoLinkValidationResult]:
    """Полный пайплайн проверки ссылки + оценка для видео-презентации (без записи в БД)."""
    cfg = config or LinkValidationConfig()
    client = probe_client or HttpProbeClient(cfg)
    normal = normalize_url(url, cfg)

    if not normal.normalized_url:
        lr = LinkValidationResult(
            originalUrl=url,
            normalizedUrl=None,
            isValidFormat=False,
            isReachable=False,
            availabilityStatus="invalid",
            provider="unknown",
            resourceType="unknown",
            statusCode=None,
            contentType=None,
            contentLength=None,
            redirected=False,
            redirectCount=0,
            responseTimeMs=None,
            warnings=normal.warnings,
            errors=normal.errors or ["Invalid URL"],
            confidence=0.0,
        )
        vr = video_result_for_invalid_url(url, "Некорректный адрес ссылки.")
        return lr, vr

    parsed, validation_warnings, validation_errors = validate_url_format(normal.normalized_url, cfg)
    if not parsed:
        lr = LinkValidationResult(
            originalUrl=url,
            normalizedUrl=normal.normalized_url,
            isValidFormat=False,
            isReachable=False,
            availabilityStatus="invalid",
            provider="unknown",
            resourceType="unknown",
            statusCode=None,
            contentType=None,
            contentLength=None,
            redirected=False,
            redirectCount=0,
            responseTimeMs=None,
            warnings=normal.warnings + validation_warnings,
            errors=normal.errors + validation_errors,
            confidence=0.0,
        )
        msg = (normal.errors + validation_errors)[0] if (normal.errors + validation_errors) else "Некорректный адрес ссылки."
        vr = video_result_for_invalid_url(url, msg)
        return lr, vr

    probe = client.probe(parsed.normalized_url)
    classify_target = probe.final_url or parsed.normalized_url
    classification = classify_url(classify_target, probe.content_type, cfg)
    cloud_warnings, cloud_errors = cloud_access_hints(classification, probe)
    availability = determine_availability(True, probe, classification, cloud_errors)

    warnings = normal.warnings + validation_warnings + classification.warnings + cloud_warnings + availability.warnings
    errors = normal.errors + validation_errors + availability.errors

    lr = LinkValidationResult(
        originalUrl=url,
        normalizedUrl=parsed.normalized_url,
        isValidFormat=True,
        isReachable=availability.is_reachable,
        availabilityStatus=availability.status,
        provider=classification.provider,
        resourceType=classification.resource_type,
        statusCode=probe.status_code,
        contentType=probe.content_type,
        contentLength=probe.content_length,
        redirected=probe.redirected,
        redirectCount=probe.redirect_count,
        responseTimeMs=probe.response_time_ms,
        warnings=warnings,
        errors=errors,
        confidence=_confidence_score(
            is_valid=True,
            reachable=availability.is_reachable,
            warnings=warnings,
            errors=errors,
        ),
    )

    vr = evaluate_presentation_video(
        original_url=url,
        normalized_url=parsed.normalized_url,
        probe=probe,
        classification=classification,
        is_reachable=availability.is_reachable,
        availability_errors=availability.errors,
        config=cfg,
        probe_client=client,
    )
    return lr, vr


def validate_presentation_video_only(
    url: str,
    config: LinkValidationConfig | None = None,
    probe_client: HttpProbeClient | None = None,
) -> VideoLinkValidationResult:
    """Только результат для видео-презентации (без записи в БД)."""
    _, vr = run_candidate_link_pipeline(url, config=config, probe_client=probe_client)
    return vr


def validate_candidate_link(
    db: Session,
    payload: LinkValidationRequest,
    config: LinkValidationConfig | None = None,
    probe_client: HttpProbeClient | None = None,
) -> LinkValidationResult:
    cfg = config or LinkValidationConfig()
    result, _ = run_candidate_link_pipeline(payload.url, config=cfg, probe_client=probe_client)
    link_validation_repository.create_link_validation_result(db, payload.application_id, result)
    db.commit()
    return result


def validate_presentation_video_endpoint(
    payload: LinkValidationRequest,
    config: LinkValidationConfig | None = None,
    probe_client: HttpProbeClient | None = None,
) -> VideoLinkValidationResult:
    """Пайплайн проверки + видео-презентация; запись в link_validation не выполняется."""
    _, vr = run_candidate_link_pipeline(payload.url, config=config, probe_client=probe_client)
    return vr


def validate_education_presentation_video_url(url: str | None) -> None:
    """Бросает ValueError с текстом на русском, если ссылка не подходит для видео-презентации."""
    s = (url or "").strip()
    if not s:
        return
    vr = validate_presentation_video_only(s)
    if vr.isValid:
        return
    detail = (vr.errors[0] if vr.errors else None) or "Укажите корректную ссылку на видеопрезентацию."
    raise ValueError(detail)
