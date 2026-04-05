"""Section review scores — recommended score computation and CRUD.

Each tab has 3 score parameters rated 1-5. The platform computes recommended
values from processed signals; reviewers can override with manual scores.
"""

from __future__ import annotations

import math
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import TextAnalysisRun
from invision_api.models.commission import SectionReviewScore
from invision_api.models.data_check_unit_result import DataCheckUnitResult
from invision_api.models.enums import DataCheckUnitType
from invision_api.commission.application import audit as commission_audit
from invision_api.repositories import data_check_repository
from invision_api.services.data_check.status_service import TERMINAL_UNIT_STATUSES

from invision_api.services.motivation_heuristics import (
    compute_motivation_signals,
    motivation_subscores_from_signals,
)
from invision_api.commission.application.section_score_explanation import build_reviewer_facing_explanation


_ScoreConfig = list[dict[str, str]]

SECTION_SCORE_CONFIGS: dict[str, _ScoreConfig] = {
    "personal": [
        {"key": "data_completeness", "label": "Полнота данных"},
        {"key": "document_correctness", "label": "Корректность документов"},
        {"key": "review_readiness", "label": "Готовность к review"},
    ],
    "test": [
        {"key": "leadership_potential", "label": "Лидерский потенциал"},
        {"key": "profile_stability", "label": "Устойчивость профиля"},
        {"key": "team_interaction", "label": "Командное взаимодействие"},
    ],
    "motivation": [
        {"key": "motivation_level", "label": "Мотивированность"},
        {"key": "choice_awareness", "label": "Осознанность выбора"},
        {"key": "specificity", "label": "Конкретика"},
    ],
    "path": [
        {"key": "initiative", "label": "Инициативность"},
        {"key": "resilience", "label": "Устойчивость"},
        {"key": "reflection_growth", "label": "Рефлексия и рост"},
    ],
    "achievements": [
        {"key": "achievement_level", "label": "Уровень достижений"},
        {"key": "personal_contribution", "label": "Личный вклад"},
        {"key": "confirmability", "label": "Подтверждённость"},
    ],
}


def _clamp(val: float, lo: int = 1, hi: int = 5) -> int:
    return max(lo, min(hi, round(val)))


def _get_analysis_run(db: Session, application_id: UUID, block_key: str) -> TextAnalysisRun | None:
    return db.scalars(
        select(TextAnalysisRun)
        .where(TextAnalysisRun.application_id == application_id, TextAnalysisRun.block_key == block_key)
        .order_by(TextAnalysisRun.created_at.desc())
    ).first()


def _get_preferred_analysis_run(db: Session, application_id: UUID, block_key: str) -> TextAnalysisRun | None:
    """Prefer post-submit analysis for reviewer scoring (fallback to latest)."""
    runs = list(
        db.scalars(
            select(TextAnalysisRun)
            .where(TextAnalysisRun.application_id == application_id, TextAnalysisRun.block_key == block_key)
            .order_by(TextAnalysisRun.created_at.desc())
        ).all()
    )
    for run in runs:
        if str(run.source_kind or "").lower() == "post_submit":
            return run
    return runs[0] if runs else None


def _compute_personal_scores(db: Session, application_id: UUID) -> dict[str, int]:
    from invision_api.repositories import admissions_repository

    scores: dict[str, int] = {}

    app = admissions_repository.get_application_by_id(db, application_id)
    if app:
        section_states = {ss.section_key: ss for ss in (app.section_states or [])}
        required = ["personal", "contact", "education"]
        filled = sum(1 for s in required if s in section_states and section_states[s].is_complete)
        scores["data_completeness"] = _clamp(math.ceil(filled / len(required) * 5))
    else:
        scores["data_completeness"] = 1

    runs = data_check_repository.list_runs_for_application(db, application_id)
    unit_map: dict[str, DataCheckUnitResult] = {}
    if runs:
        for r in data_check_repository.list_unit_results_for_run(db, runs[0].id):
            unit_map[r.unit_type] = r

    doc_units = [
        unit_map.get(DataCheckUnitType.certificate_validation.value),
    ]
    doc_ok = sum(1 for u in doc_units if u and u.status == "completed")
    doc_total = sum(1 for u in doc_units if u)
    if doc_total > 0:
        scores["document_correctness"] = _clamp(math.ceil(doc_ok / doc_total * 5))
    else:
        scores["document_correctness"] = 3

    terminal = sum(1 for u in unit_map.values() if u.status in TERMINAL_UNIT_STATUSES)
    total = len(unit_map) if unit_map else 1
    manual_needed = sum(1 for u in unit_map.values() if u.manual_review_required)
    if terminal == total and manual_needed == 0:
        scores["review_readiness"] = 5
    elif terminal == total:
        scores["review_readiness"] = 3
    else:
        scores["review_readiness"] = _clamp(math.ceil(terminal / total * 4))

    return scores


def _compute_test_scores(db: Session, application_id: UUID) -> dict[str, int]:
    scores: dict[str, int] = {}
    run = _get_analysis_run(db, application_id, "test_profile")
    profile = ((run.explanations or {}).get("profile", {})) if run else {}
    ranking = profile.get("ranking", [])
    flags = profile.get("flags", {})
    meta = profile.get("meta", {})

    ini_score = 3
    for entry in ranking:
        if entry.get("trait") == "INI":
            raw = entry.get("score", 0)
            total = sum(e.get("score", 0) for e in ranking) or 1
            ini_score = _clamp(math.ceil(raw / total * 5 * len(ranking)))
            break
    scores["leadership_potential"] = ini_score

    answer_count = meta.get("answerCount", 0)
    expected = meta.get("expectedQuestionCount", 40)
    consistency_ok = not flags.get("consistencyWarning", False)
    social_ok = not flags.get("shouldReviewForSocialDesirability", False)
    stability = 5
    if answer_count < expected:
        stability -= 1
    if not consistency_ok:
        stability -= 1
    if not social_ok:
        stability -= 1
    scores["profile_stability"] = _clamp(stability)

    col_score = 3
    for entry in ranking:
        if entry.get("trait") == "COL":
            raw = entry.get("score", 0)
            total = sum(e.get("score", 0) for e in ranking) or 1
            col_score = _clamp(math.ceil(raw / total * 5 * len(ranking)))
            break
    scores["team_interaction"] = col_score

    return scores


def _path_section_signal(section_signals: dict[str, Any], primary: str, *fallbacks: str) -> float | None:
    for key in (primary,) + fallbacks:
        v = section_signals.get(key)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return None


def _path_score_from_signal(signal: float | None) -> int:
    if signal is None:
        return 3
    if signal >= 0.75:
        return 5
    if signal >= 0.55:
        return 4
    if signal >= 0.35:
        return 3
    if signal >= 0.20:
        return 2
    return 1


def _path_quality_metrics(run: TextAnalysisRun | None) -> tuple[float, float, bool]:
    """Returns non_spam_ratio, evidence_ratio, strong_negative."""
    if not run:
        return 0.0, 0.0, False
    exp = run.explanations if isinstance(run.explanations, dict) else {}
    per_question = (exp or {}).get("per_question") or {}
    if isinstance(per_question, dict):
        items = [v for v in per_question.values() if isinstance(v, dict)]
    elif isinstance(per_question, list):
        items = [v for v in per_question if isinstance(v, dict)]
    else:
        items = []

    total = len(items)
    if total == 0:
        return 0.0, 0.0, False

    non_spam = 0
    evidence_hits = 0
    spam_count = 0
    for item in items:
        spam_ok = (item.get("spam_check") or {}).get("ok")
        if spam_ok is False:
            spam_count += 1
        else:
            non_spam += 1

        heur = item.get("heuristics") if isinstance(item.get("heuristics"), dict) else {}
        action = float(heur.get("action_score") or 0.0)
        reflection = float(heur.get("reflection_score") or 0.0)
        concrete = float(heur.get("concrete_score") or 0.0)
        key_sentences = item.get("key_sentences")
        has_key_sentence = isinstance(key_sentences, list) and any(str(s).strip() for s in key_sentences)
        if (action + reflection + concrete) >= 0.55 or has_key_sentence:
            evidence_hits += 1

    non_spam_ratio = non_spam / total
    evidence_ratio = evidence_hits / total
    manual_flag = bool((run.flags or {}).get("manual_review_required"))
    strong_negative = spam_count >= 2 or (manual_flag and spam_count >= 1 and total >= 2)
    return non_spam_ratio, evidence_ratio, strong_negative


_PATH_EVIDENCE_MARKERS: dict[str, tuple[str, ...]] = {
    "initiative": (
        "инициатив",
        "самостоятель",
        "организ",
        "созд",
        "запуст",
        "проект",
    ),
    "resilience": (
        "труд",
        "слож",
        "преодол",
        "барьер",
        "ошиб",
        "неувер",
    ),
    "reflection_growth": (
        "понял",
        "осоз",
        "вывод",
        "рост",
        "измен",
        "подход",
        "науч",
    ),
}


def _path_evidence_hits(
    run: TextAnalysisRun | None,
    validated_section: Any | None,
) -> dict[str, int]:
    hits = {"initiative": 0, "resilience": 0, "reflection_growth": 0}
    seen: dict[str, set[str]] = {k: set() for k in hits}

    def _register(text: str) -> None:
        t = str(text or "").strip()
        if not t:
            return
        low = t.lower()
        norm = " ".join(low.split())
        for key, markers in _PATH_EVIDENCE_MARKERS.items():
            if any(marker in low for marker in markers) and norm not in seen[key]:
                seen[key].add(norm)
                hits[key] += 1

    if validated_section and hasattr(validated_section, "answers"):
        answers = getattr(validated_section, "answers", {}) or {}
        if isinstance(answers, dict):
            for answer in answers.values():
                _register(getattr(answer, "text", None) or "")

    exp = run.explanations if isinstance(getattr(run, "explanations", None), dict) else {}
    per_question = (exp or {}).get("per_question") or {}
    if isinstance(per_question, dict):
        pq_items = [v for v in per_question.values() if isinstance(v, dict)]
    elif isinstance(per_question, list):
        pq_items = [v for v in per_question if isinstance(v, dict)]
    else:
        pq_items = []

    for item in pq_items:
        for sentence in (item.get("key_sentences") or []):
            _register(sentence)

    return hits


def _compute_motivation_scores(db: Session, application_id: UUID) -> dict[str, int]:
    from invision_api.models.enums import SectionKey
    from invision_api.services.data_check.utils import get_validated_section

    validated = get_validated_section(db, application_id=application_id, section_key=SectionKey.motivation_goals)
    narrative = (getattr(validated, "narrative", None) or "").strip() if validated else ""
    if narrative:
        signals = compute_motivation_signals(narrative)
        return motivation_subscores_from_signals(signals)

    run = _get_analysis_run(db, application_id, "motivation_goals")
    stored = ((run.explanations or {}).get("signals", {})) if run else {}
    if stored:
        excerpt = ((run.explanations or {}).get("summary") or "") if run else ""
        base = compute_motivation_signals(excerpt) if excerpt.strip() else compute_motivation_signals("")
        merged = {**base, **stored}
        return motivation_subscores_from_signals(merged)

    return {"motivation_level": 3, "choice_awareness": 3, "specificity": 3}


def _compute_path_scores(db: Session, application_id: UUID) -> dict[str, int]:
    from invision_api.models.enums import SectionKey
    from invision_api.services.data_check.utils import get_validated_section

    scores: dict[str, int] = {}
    run = _get_preferred_analysis_run(db, application_id, "growth_journey")
    exp = run.explanations if run else None
    section_signals: dict[str, Any] = (exp or {}).get("section_signals") or {}
    if not section_signals and run and getattr(run, "dimensions", None):
        section_signals = (run.dimensions or {}).get("section_signals") or {}

    scores["initiative"] = _path_score_from_signal(
        _path_section_signal(section_signals, "initiative", "initiative_score")
    )
    scores["resilience"] = _path_score_from_signal(
        _path_section_signal(section_signals, "resilience", "resilience_score")
    )
    scores["reflection_growth"] = _path_score_from_signal(
        _path_section_signal(section_signals, "growth", "growth_score", "reflection_growth")
    )

    non_spam_ratio, evidence_ratio, strong_negative = _path_quality_metrics(run)
    validated_path = None
    if db is not None:
        try:
            validated_path = get_validated_section(
                db,
                application_id=application_id,
                section_key=SectionKey.growth_journey,
            )
        except Exception:
            validated_path = None
    evidence_hits = _path_evidence_hits(run, validated_path)

    if not strong_negative:
        for key in ("initiative", "resilience", "reflection_growth"):
            scores[key] = max(scores[key], 2)
            if evidence_hits.get(key, 0) >= 2 and scores[key] < 4:
                scores[key] += 1

    if non_spam_ratio >= 0.8 and evidence_ratio >= 0.6:
        for key in ("initiative", "resilience", "reflection_growth"):
            scores[key] = max(scores[key], 3)

    return scores


def _compute_achievements_scores(db: Session, application_id: UUID) -> dict[str, int]:
    scores: dict[str, int] = {}
    run = _get_analysis_run(db, application_id, "achievements_activities")
    signals = ((run.explanations or {}).get("signals", {})) if run else {}

    impact = signals.get("impact_markers", 0)
    word_count = signals.get("word_count", 0)
    if impact >= 3 and word_count >= 100:
        scores["achievement_level"] = 5
    elif impact >= 2 or word_count >= 80:
        scores["achievement_level"] = 4
    elif impact >= 1 or word_count >= 50:
        scores["achievement_level"] = 3
    elif word_count >= 20:
        scores["achievement_level"] = 2
    else:
        scores["achievement_level"] = 1

    has_role = signals.get("has_role", False)
    has_year = signals.get("has_year", False)
    contribution = 3
    if has_role:
        contribution += 1
    if has_year:
        contribution += 1
    if not has_role and impact == 0:
        contribution = 1
    scores["personal_contribution"] = _clamp(contribution)

    links_count = signals.get("links_count", 0)
    runs = data_check_repository.list_runs_for_application(db, application_id)
    link_reachable = 0
    link_total = 0
    if runs:
        for r in data_check_repository.list_unit_results_for_run(db, runs[0].id):
            if r.unit_type == DataCheckUnitType.link_validation.value:
                payload = r.result_payload or {}
                checked = payload.get("links", [])
                link_total = len(checked)
                link_reachable = sum(1 for ln in checked if ln.get("isReachable"))

    if links_count >= 2 and link_reachable == link_total and link_total > 0:
        scores["confirmability"] = 5
    elif links_count >= 1 and link_reachable > 0:
        scores["confirmability"] = 4
    elif links_count >= 1:
        scores["confirmability"] = 3
    elif has_year:
        scores["confirmability"] = 2
    else:
        scores["confirmability"] = 1

    return scores


_COMPUTE_MAP = {
    "personal": _compute_personal_scores,
    "test": _compute_test_scores,
    "motivation": _compute_motivation_scores,
    "path": _compute_path_scores,
    "achievements": _compute_achievements_scores,
}


def compute_recommended_scores(db: Session, application_id: UUID, section: str) -> dict[str, int]:
    fn = _COMPUTE_MAP.get(section)
    if not fn:
        return {}
    return fn(db, application_id)


def get_section_scores(
    db: Session,
    *,
    application_id: UUID,
    section: str,
    reviewer_user_id: UUID,
) -> dict[str, Any]:
    config = SECTION_SCORE_CONFIGS.get(section)
    if not config:
        return {
            "section": section,
            "items": [],
            "totalScore": 0,
            "maxTotalScore": 0,
            "aggregateRecommendedScore": 3,
            "aggregateRecommendationExplanation": "",
        }

    recommended = compute_recommended_scores(db, application_id, section)

    saved_rows = db.scalars(
        select(SectionReviewScore).where(
            SectionReviewScore.application_id == application_id,
            SectionReviewScore.reviewer_user_id == reviewer_user_id,
            SectionReviewScore.section == section,
        )
    ).all()
    saved_map = {r.score_key: r for r in saved_rows}

    items: list[dict[str, Any]] = []
    total = 0
    rec_values: list[int] = []
    for cfg in config:
        key = cfg["key"]
        rec = recommended.get(key, 3)
        rec_values.append(rec)
        saved = saved_map.get(key)
        manual = saved.manual_score if saved else None
        effective = manual if manual is not None else rec
        items.append({
            "key": key,
            "label": cfg["label"],
            "recommendedScore": rec,
            "manualScore": manual,
            "effectiveScore": effective,
        })
        total += effective

    aggregate_recommended = max(1, min(5, round(sum(rec_values) / len(rec_values)))) if rec_values else 3
    if section == "path":
        run = _get_preferred_analysis_run(db, application_id, "growth_journey")
        non_spam_ratio, evidence_ratio, strong_negative = _path_quality_metrics(run)
        if not strong_negative and non_spam_ratio >= 0.8 and evidence_ratio >= 0.6:
            aggregate_recommended = max(3, aggregate_recommended)
    explanation = build_reviewer_facing_explanation(
        db, application_id, section, items, aggregate_recommended
    )

    return {
        "section": section,
        "items": items,
        "totalScore": total,
        "maxTotalScore": len(config) * 5,
        "aggregateRecommendedScore": aggregate_recommended,
        "aggregateRecommendationExplanation": explanation,
    }


def save_section_scores(
    db: Session,
    *,
    application_id: UUID,
    section: str,
    reviewer_user_id: UUID,
    scores: list[dict[str, int]],
) -> dict[str, Any]:
    config = SECTION_SCORE_CONFIGS.get(section)
    if not config:
        return {"ok": False}

    valid_keys = {c["key"] for c in config}
    recommended = compute_recommended_scores(db, application_id, section)

    applied_scores: dict[str, int] = {}
    for item in scores:
        key = item.get("key", "")
        score_val = item.get("score")
        if key not in valid_keys or not isinstance(score_val, int) or not (1 <= score_val <= 5):
            continue

        row = db.scalars(
            select(SectionReviewScore).where(
                SectionReviewScore.application_id == application_id,
                SectionReviewScore.reviewer_user_id == reviewer_user_id,
                SectionReviewScore.section == section,
                SectionReviewScore.score_key == key,
            )
        ).first()

        rec = recommended.get(key, 3)
        if row:
            row.manual_score = score_val
            row.recommended_score = rec
        else:
            row = SectionReviewScore(
                application_id=application_id,
                reviewer_user_id=reviewer_user_id,
                section=section,
                score_key=key,
                recommended_score=rec,
                manual_score=score_val,
            )
            db.add(row)
        applied_scores[key] = score_val

    db.flush()
    if applied_scores:
        commission_audit.write_event(
            db,
            event_type="section_scores_updated",
            entity_type="application",
            entity_id=application_id,
            actor_user_id=reviewer_user_id,
            after={
                "section": section,
                "scores": applied_scores,
            },
        )
    return get_section_scores(
        db,
        application_id=application_id,
        section=section,
        reviewer_user_id=reviewer_user_id,
    )
