"""Human-readable explanations for recommended section scores (commission UI).

Keeps aggregation math in section_score_service; this module only formats reviewer-facing text.
"""

from __future__ import annotations
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import TextAnalysisRun
from invision_api.models.enums import DataCheckUnitType, SectionKey
from invision_api.repositories import data_check_repository
from invision_api.commission.application.reviewer_text_sanitizer import (
    centered_keyword_snippet,
    dedupe_keep_order,
    sanitize_reviewer_text,
    split_sentences,
)
from invision_api.services.data_check.utils import get_validated_section
from invision_api.services.motivation_heuristics import compute_motivation_signals

_SCOPE_INTRO: dict[str, str] = {
    "personal": "личных данных, контактов и документов",
    "test": "теста на тип личности",
    "motivation": "мотивационного письма",
    "path": "ответов в разделе «Путь»",
    "achievements": "раздела «Достижения»",
}


def _fetch_analysis_run(db: Session, application_id: UUID, block_key: str) -> TextAnalysisRun | None:
    return db.scalars(
        select(TextAnalysisRun)
        .where(TextAnalysisRun.application_id == application_id, TextAnalysisRun.block_key == block_key)
        .order_by(TextAnalysisRun.created_at.desc())
    ).first()


def _fetch_preferred_analysis_run(db: Session, application_id: UUID, block_key: str) -> TextAnalysisRun | None:
    """Prefer post-submit run for reviewer-facing scoring/explanations."""
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


def _motivation_signals_for_explanation(db: Session, application_id: UUID) -> dict[str, Any]:
    validated = get_validated_section(db, application_id=application_id, section_key=SectionKey.motivation_goals)
    narrative = (getattr(validated, "narrative", None) or "").strip() if validated else ""
    if narrative:
        return compute_motivation_signals(narrative)
    run = _fetch_analysis_run(db, application_id, "motivation_goals")
    stored = ((run.explanations or {}).get("signals", {})) if run else {}
    excerpt = ((run.explanations or {}).get("summary") or "") if run else ""
    base = compute_motivation_signals(excerpt) if excerpt.strip() else compute_motivation_signals("")
    return {**base, **stored}


def _motivation_evidence_paragraph(key: str, score: int, s: dict[str, Any]) -> str:
    """UI copy only: uses raw signals internally; must not echo numeric features."""
    wc = int(s.get("word_count") or 0)
    md = float(s.get("motivation_density") or 0)
    ir = float(s.get("intrinsic_ratio") or 0.5)
    ch = int(s.get("choice_pattern_hits") or 0)
    pf = int(s.get("program_fit_hits") or 0)
    ev = float(s.get("evidence_density") or 0)
    has_d = bool(s.get("has_digits"))
    sm = int(s.get("structure_markers") or 0)

    def tail_not_max(hint: str) -> str:
        if score >= 5:
            return ""
        return f" {hint}"

    if key == "motivation_level":
        if md >= 0.18 and ir >= 0.45:
            core = (
                "В письме заметно стремление к развитию и личная вовлечённость; тема роста звучит уверенно."
            )
        elif md >= 0.1:
            core = "Тема развития присутствует, но звучит неравномерно: не на каждом фрагменте ясно, зачем именно это обучение."
        else:
            core = "Мало устойчивых формулировок о собственной мотивации и интересе к росту; картина выглядит бледной."
        return core + tail_not_max(
            "Для более сильной оценки полезно явнее связать личные цели с учёбой и следующими шагами."
        )

    if key == "choice_awareness":
        longish = wc >= 150
        if ch >= 1 or pf >= 3:
            core = (
                "Кандидат отделяет выбор этой программы от «просто учиться»: есть сопоставление вариантов и связь с форматом, "
                "ценностями или средой — это как раз про осознанность выбора."
            )
        elif longish:
            core = (
                "Письмо развёрнутое, но смысл именно осознанного выбора среды и программы выражен не на всём протяжении текста."
            )
        else:
            core = (
                "Обоснование, почему подходит именно такой формат и среда, выражено слабо или фрагментарно."
            )
        return core + tail_not_max(
            "Чтобы усилить балл, полезнее явно объяснить альтернативы и почему этот путь — осознанный."
        )

    if key == "specificity":
        if ev >= 0.12 and (has_d or sm >= 2):
            core = "В тексте есть примеры и опора на факты; детали помогают представить ситуацию, а не только общие намерения."
        elif ev >= 0.06:
            core = "Примеры и детали встречаются, но не держат всё письмо сквозь: часть формулировок остаётся общей."
        else:
            core = "Описание в основном обобщённое: мало опоры на конкретные эпизоды и факты из опыта."
        return core + tail_not_max(
            "Для более высокой оценки полезно добавить предметные эпизоды и шаги, к которым можно вернуться на интервью."
        )

    return "Оценка сформирована по автоматическому разбору текста этого раздела."


_PATH_MARKERS: dict[str, tuple[str, ...]] = {
    "initiative": (
        "инициатив",
        "самостоятель",
        "сам ",
        "сама ",
        "созд",
        "запуст",
        "организ",
        "проект",
        "оку",
        "команд",
        "структур",
    ),
    "resilience": (
        "труд",
        "слож",
        "барьер",
        "страх",
        "ошиб",
        "преодол",
        "неувер",
        "обратн",
        "сдава",
    ),
    "reflection_growth": (
        "понял",
        "осоз",
        "вывод",
        "рост",
        "измен",
        "науч",
        "рефлекс",
        "подход",
        "дисциплин",
        "улучш",
    ),
}


def _extract_evidence_sentences(text: str) -> list[str]:
    out: list[str] = []
    for sentence in split_sentences(text):
        clean = sanitize_reviewer_text(
            sentence,
            max_sentences=1,
            max_sentence_chars=180,
            max_total_chars=180,
        )
        if clean:
            out.append(clean)
    return dedupe_keep_order(out)


def _collect_path_evidence(
    validated_section: Any | None,
    per_question: dict[str, Any] | list[Any] | None,
) -> dict[str, list[str]]:
    by_key: dict[str, list[str]] = {"initiative": [], "resilience": [], "reflection_growth": []}

    def register(text: str) -> None:
        cleaned = sanitize_reviewer_text(
            text,
            max_sentences=2,
            max_sentence_chars=220,
            max_total_chars=220,
        )
        if not cleaned:
            return
        lower = cleaned.lower()
        for key, markers in _PATH_MARKERS.items():
            if any(marker in lower for marker in markers):
                snippet = centered_keyword_snippet(cleaned, markers, max_chars=180)
                out = sanitize_reviewer_text(
                    snippet,
                    max_sentences=1,
                    max_sentence_chars=180,
                    max_total_chars=180,
                )
                if out:
                    by_key[key].append(out)

    if validated_section and hasattr(validated_section, "answers"):
        answers = getattr(validated_section, "answers", {}) or {}
        if isinstance(answers, dict):
            for answer in answers.values():
                txt = (getattr(answer, "text", None) or "").strip()
                for sent in _extract_evidence_sentences(txt):
                    register(sent)

    pq_items: list[Any]
    if isinstance(per_question, dict):
        pq_items = list(per_question.values())
    elif isinstance(per_question, list):
        pq_items = per_question
    else:
        pq_items = []

    for item in pq_items:
        key_sentences = (item or {}).get("key_sentences") if isinstance(item, dict) else None
        if not isinstance(key_sentences, list):
            continue
        for sent in key_sentences:
            clean = sanitize_reviewer_text(
                str(sent),
                max_sentences=1,
                max_sentence_chars=180,
                max_total_chars=180,
            )
            if clean:
                register(clean)

    return {k: dedupe_keep_order(v)[:3] for k, v in by_key.items()}


def _path_evidence_paragraph(
    key: str,
    score: int,
    evidence: list[str],
) -> str:
    evidence_line = f"В ответах есть конкретный пример: «{evidence[0]}». " if evidence else ""
    no_evidence_line = "Пока недостаточно фактов для уверенного вывода по этому подкритерию. "

    if key == "initiative":
        if score >= 4:
            return (
                f"{evidence_line}Кандидат показывает инициативу не только в словах, но и в действиях. "
                "Чтобы усилить аргументацию, на интервью можно уточнить масштаб и устойчивость личной роли."
            )
        if score == 3:
            return (
                f"{evidence_line}Инициативность проявляется, но не во всех эпизодах одинаково ясно. "
                "На интервью стоит уточнить масштаб личной роли."
            )
        return (
            f"{evidence_line or no_evidence_line}"
            "Сейчас аргументация по инициативности слабая: нужны дополнительные примеры самостоятельных действий."
        ).strip()

    if key == "resilience":
        if score >= 4:
            return (
                f"{evidence_line}В разделе заметна линия преодоления трудностей и готовность доводить работу до результата. "
                "Чтобы снять риски, стоит уточнить, в каких условиях это проявлялось и какой был итог."
            )
        if score == 3:
            return (
                f"{evidence_line}Трудности упомянуты, но глубина преодоления раскрыта частично. "
                "Нужна дополнительная конкретика по действиям в сложных ситуациях."
            )
        return (
            f"{evidence_line or no_evidence_line}"
            "По устойчивости фактов пока недостаточно: стоит уточнить, как кандидат действовал при давлении и неудачах."
        ).strip()

    # reflection_growth
    if score >= 4:
        return (
            f"{evidence_line}Кандидат демонстрирует рефлексию: видны выводы из опыта и изменение подхода к развитию. "
            "Для полноты можно уточнить, как эти выводы повлияли на последующие действия."
        )
    if score == 3:
        return (
            f"{evidence_line}Элементы рефлексии есть, но связка «опыт -> вывод -> следующий шаг» выражена не везде одинаково. "
            "Это скорее средний уровень с потенциалом роста."
        )
    return (
        f"{evidence_line or no_evidence_line}"
        "Рефлексия и рост выражены слабо: требуется больше осмысленных выводов о собственном развитии."
    ).strip()


def _path_conclusion(*, aggregate: int, evidence_map: dict[str, list[str]]) -> str:
    evidence_cnt = sum(1 for vals in evidence_map.values() if vals)
    if aggregate >= 4:
        return (
            "Итог: ответы выглядят целостными и зрелыми. В них есть самостоятельность, "
            "преодоление трудностей и внятная рефлексия. Это сильная рекомендация, "
            "которую комиссия подтверждает по полным ответам кандидата."
        )
    if aggregate == 3:
        return (
            "Итог: раздел в целом выглядит содержательно и тянет на уверенный средний уровень. "
            "Есть реальные сигналы роста и действий, но часть деталей лучше уточнить на интервью."
        )
    if evidence_cnt >= 2:
        return (
            "Итог: в разделе есть смысловые опоры, но их пока недостаточно для высокой рекомендации. "
            "Решение стоит принимать после ручного чтения всех ответов."
        )
    return (
        "Итог: по текущим материалам аргументация ограничена. Нужен дополнительный ручной разбор ответов "
        "перед финальной оценкой комиссии."
    )


def _achievements_criterion_text(
    key: str,
    score: int,
    signals: dict[str, Any],
    *,
    link_reachable: int,
    link_total: int,
) -> str:
    impact = int(signals.get("impact_markers") or 0)
    wc = int(signals.get("word_count") or 0)

    if key == "achievement_level":
        rich_text = wc >= 100 or impact >= 2
        if score >= 5:
            if rich_text:
                return (
                    "Описание достижений содержательное: читается масштаб и влияние, есть опора на факты и результат; картина насыщенная."
                )
            return (
                "Достижения представлены так, что удаётся оценить уровень и смысл; при необходимости детали можно уточнить на интервью."
            )
        if score >= 4:
            return (
                "Достижения описаны с заметной конкретикой; масштаб и влияние читаются, без полноты по всем осям."
            )
        if score == 3:
            return (
                "Описание достижений умеренно детализировано; есть факты, но не везде раскрыт масштаб и результат."
            )
        if score == 2:
            return (
                "Текст короткий или без явных примеров результата и влияния; картина достижений пока неполная."
            )
        return (
            "Материалов для уверенной оценки уровня достижений в тексте мало."
        )

    if key == "personal_contribution":
        has_role = bool(signals.get("has_role"))
        has_year = bool(signals.get("has_year"))
        if score >= 5:
            return (
                "В описании явно присутствуют роль кандидата и временные привязки; личный вклад читается отчётливо."
            )
        if score >= 4:
            return (
                "Личный вклад прослеживается"
                + (" (роль указана)" if has_role else "")
                + (" (год указан)" if has_year else "")
                + "; детали можно уточнить при обсуждении."
            )
        if score == 3:
            return (
                "Вклад описан частично: не все элементы (роль, сроки) закреплены в тексте одинаково явно."
            )
        if score == 2:
            return (
                "Роль и личное участие в ситуациях раскрыты слабо; опора в основном на общий рассказ."
            )
        return (
            "Личный вклад по тексту раздела выделить трудно; рекомендуется опираться на первоисточники и уточнения."
        )

    if key == "confirmability":
        if score >= 5 and link_total > 0:
            return (
                "Есть несколько ссылок на подтверждения; по проверкам доступность ссылок выглядит согласованной."
            )
        if score >= 4:
            return (
                "Ссылочные подтверждения присутствуют; часть из них доступна для проверки."
            )
        if score == 3:
            return (
                "Ссылки указаны, но не все ведут к устойчиво проверяемым материалам; имеет смысл свериться вручную."
            )
        if score == 2:
            return (
                "Подтверждений через ссылки мало или они слабо связаны с описанным опытом."
            )
        return (
            "Независимые подтверждения в материалах выражены слабо; оценка опирается в основном на текст раздела."
        )

    return "Оценка сформирована по автоматическому разбору раздела «Достижения»."


def _personal_criterion_text(key: str, score: int) -> str:
    if key == "data_completeness":
        if score >= 5:
            return "Ключевые блоки личных данных и контактов заполнены; картина заявки для первичного просмотра цельная."
        if score >= 4:
            return "Основные секции заполнены; мелкие пробелы возможны, но базовая полнота для review достигнута."
        if score == 3:
            return "Заполненность умеренная: часть обязательных блоков может требовать досборки или уточнения."
        if score == 2:
            return "Заметны пробелы в обязательных данных; комиссии полезно проверить список секций до обсуждения."
        return "Полнота данных низкая; без доработки анкеты опора на материалы ограничена."

    if key == "document_correctness":
        if score >= 5:
            return "По данным проверки документы проходят ожидаемые шаги валидации без критичных отметок."
        if score >= 4:
            return "Документы в целом в порядке; возможны точечные замечания по отдельным вложениям."
        if score == 3:
            return "Есть нейтральные или промежуточные по шкале сигналы по корректности вложений; стоит просмотреть список проверок."
        if score == 2:
            return "По документам есть заметные риски или незавершённые проверки; это стоит учесть при отборе."
        return "Корректность документов по автоматическим проверкам вызывает вопросы; нужен ручной разбор."

    if key == "review_readiness":
        if score >= 5:
            return "Конвейер проверок данных в основном завершён; ручных блокеров по статусам не выявлено."
        if score >= 4:
            return "Готовность к review высокая; отдельные единицы могут ждать ручного просмотра."
        if score == 3:
            return "Часть проверок ещё не в финальном статусе; комиссии полезно свериться с панелью статусов."
        if score == 2:
            return "Много единиц в незавершённых или спорных статусах; ускоренное решение по заявке может быть преждевременным."
        return "Заявка с точки зрения готовности данных к review выглядит сырой; приоритет — довести проверки."

    return "Оценка сформирована по сводным сигналам блока личных данных."


def _test_criterion_text(key: str, score: int) -> str:
    _ = key
    if score >= 5:
        return "По данным профиля теста сигнал по этому параметру в верхней части шкалы; трактовать вместе с остальными разделами."
    if score >= 4:
        return "Показатель в тесте в верхней части распределения; использовать как дополнительный ориентир, не как единственный критерий."
    if score == 3:
        return "Значение близко к середине шкалы; сопоставляйте с поведением в интервью и текстах."
    if score == 2:
        return "Сигнал смещён в сторону ограничений; полезно сверить с фактическим контекстом заявки."
    return "Нижняя зона шкалы по этому параметру; интерпретация осторожная, в связке с другими материалами."


def _conclusion(items: list[dict[str, Any]], section: str) -> str:
    if not items:
        return "Итог: данных для смыслового вывода недостаточно."

    scored = [(int(i["recommendedScore"]), str(i["label"])) for i in items]
    hi = max(scored, key=lambda x: x[0])
    lo = min(scored, key=lambda x: x[0])

    if hi[0] == lo[0]:
        return (
            f"Итог: по {_SCOPE_SHORT(section)} профили подкритериев сейчас выровнены; комиссии полезно опереться на строки выше "
            "и при сомнениях вернуться к исходным ответам кандидата."
        )

    return (
        f"Итог: сильнее всего в автоматическом разборе выделяется «{hi[1]}»; заметнее ограничение — «{lo[1]}». "
        "Используйте это как ориентир при обсуждении, а не как итоговый вердикт без чтения материалов."
    )


def _SCOPE_SHORT(section: str) -> str:
    return {
        "motivation": "мотивационному письму",
        "path": "разделу «Путь»",
        "achievements": "достижениям",
        "personal": "личным данным",
        "test": "тесту",
    }.get(section, "разделу")


def build_reviewer_facing_explanation(
    db: Session,
    application_id: UUID,
    section: str,
    items: list[dict[str, Any]],
    aggregate: int,
) -> str:
    if not items:
        return ""

    parts = [f"«{i['label']}» — {int(i['recommendedScore'])}" for i in items]
    if section == "path":
        intro = "\n".join(
            [
                "Для раздела «Путь» рассчитаны рекомендованные баллы:",
                *parts,
            ]
        )
    elif len(parts) == 1:
        scope = _SCOPE_INTRO.get(section, "этого раздела заявки")
        intro = f"Для {scope} автоматически рассчитан рекомендуемый балл: {parts[0]}."
    elif len(parts) == 2:
        scope = _SCOPE_INTRO.get(section, "этого раздела заявки")
        intro = f"Для {scope} автоматически рассчитаны рекомендуемые баллы по подкритериям: {parts[0]} и {parts[1]}."
    else:
        scope = _SCOPE_INTRO.get(section, "этого раздела заявки")
        intro = f"Для {scope} автоматически рассчитаны три рекомендуемых балла по подкритериям: {', '.join(parts[:-1])} и {parts[-1]}."

    paragraphs: list[str] = [intro]

    if section == "motivation":
        sig = _motivation_signals_for_explanation(db, application_id)
        for it in items:
            inner_key = str(it.get("key", ""))
            sc = int(it["recommendedScore"])
            body = _motivation_evidence_paragraph(inner_key, sc, sig)
            paragraphs.append(f"«{it['label']}»: {body}")

    elif section == "path":
        run = _fetch_preferred_analysis_run(db, application_id, "growth_journey")
        exp = run.explanations if run else None
        per_question = (exp or {}).get("per_question") or {}
        validated_path = get_validated_section(
            db, application_id=application_id, section_key=SectionKey.growth_journey
        )
        evidence_map = _collect_path_evidence(validated_path, per_question)
        for it in items:
            inner_key = str(it.get("key", ""))
            sc = int(it["recommendedScore"])
            body = _path_evidence_paragraph(
                inner_key,
                sc,
                evidence_map.get(inner_key, []),
            )
            paragraphs.append(f"{it['label']}: {body}")

    elif section == "achievements":
        run = _fetch_analysis_run(db, application_id, "achievements_activities")
        signals = ((run.explanations or {}).get("signals", {})) if run else {}
        link_reachable = 0
        link_total = 0
        runs = data_check_repository.list_runs_for_application(db, application_id)
        if runs:
            for r in data_check_repository.list_unit_results_for_run(db, runs[0].id):
                if r.unit_type == DataCheckUnitType.link_validation.value:
                    payload = r.result_payload or {}
                    checked = payload.get("links", [])
                    link_total = len(checked)
                    link_reachable = sum(1 for ln in checked if ln.get("isReachable"))
        for it in items:
            inner_key = str(it.get("key", ""))
            sc = int(it["recommendedScore"])
            body = _achievements_criterion_text(
                inner_key,
                sc,
                signals,
                link_reachable=link_reachable,
                link_total=link_total,
            )
            paragraphs.append(f"«{it['label']}»: {body}")

    elif section == "personal":
        for it in items:
            inner_key = str(it.get("key", ""))
            sc = int(it["recommendedScore"])
            body = _personal_criterion_text(inner_key, sc)
            paragraphs.append(f"«{it['label']}»: {body}")

    elif section == "test":
        for it in items:
            inner_key = str(it.get("key", ""))
            sc = int(it["recommendedScore"])
            body = _test_criterion_text(inner_key, sc)
            paragraphs.append(f"«{it['label']}»: {body}")

    else:
        for it in items:
            sc = int(it["recommendedScore"])
            paragraphs.append(
                f"«{it['label']}»: Рекомендуемый балл {sc} сформирован автоматически; детали смотрите в исходных данных раздела."
            )

    if section == "path":
        paragraphs.append(_path_conclusion(aggregate=aggregate, evidence_map=evidence_map))
    else:
        paragraphs.append(_conclusion(items, section))
    paragraphs.append(f"Рекомендуемая оценка: {aggregate}")

    return "\n\n".join(paragraphs)
