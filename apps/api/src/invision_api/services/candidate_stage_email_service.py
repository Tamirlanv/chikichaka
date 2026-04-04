"""Candidate-facing emails on stage transitions (Resend), after successful DB commit."""

from __future__ import annotations

import html
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from invision_api.core.config import get_settings
from invision_api.db.session import SessionLocal
from invision_api.models.application import Application, CandidateProfile
from invision_api.services.email_delivery import send_html_email

logger = logging.getLogger(__name__)

# Aligned with apps/web/lib/application-stage.ts CANDIDATE_STAGE_PIPELINE labels
STAGE_LABEL_RU: dict[str, str] = {
    "application": "Подача анкеты",
    "initial_screening": "Проверка данных",
    "application_review": "Оценка заявки",
    "interview": "Собеседование",
    "committee_review": "Решение комиссии",
    "decision": "Результат",
}

FINAL_DECISION_LABEL_RU: dict[str, str] = {
    "move_forward": "Рекомендация к дальнейшему рассмотрению",
    "reject": "Отказ",
    "waitlist": "Лист ожидания",
    "invite_interview": "Приглашение на собеседование",
    "enrolled": "Зачисление",
}


def _stage_label(code: str) -> str:
    return STAGE_LABEL_RU.get(code, code)


def _load_candidate_email_and_name(db: Session, application_id: UUID) -> tuple[str | None, str | None]:
    app = db.scalars(
        select(Application)
        .where(Application.id == application_id)
        .options(
            selectinload(Application.candidate_profile).selectinload(CandidateProfile.user),
        )
    ).first()
    if not app or not app.candidate_profile:
        logger.warning("candidate_stage_email: no profile for application_id=%s", application_id)
        return None, None
    user = app.candidate_profile.user
    if not user or not user.email:
        logger.warning("candidate_stage_email: no user/email for application_id=%s", application_id)
        return None, None
    first = (app.candidate_profile.first_name or "").strip() or None
    return user.email.strip().lower(), first


def _wrap_html(body_paragraphs: list[str], *, title: str) -> str:
    settings = get_settings()
    site = html.escape(settings.app_public_url.rstrip("/"))
    safe_title = html.escape(title)
    parts = [f"<p>{html.escape(p)}</p>" for p in body_paragraphs]
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{safe_title}</title></head><body>
<h1 style="font-size:18px;font-weight:600;">{safe_title}</h1>
{"".join(parts)}
<p style="color:#666;font-size:14px;margin-top:24px;">С уважением,<br/>команда inVision U<br/>
<a href="{site}">{site}</a></p>
</body></html>"""


def send_stage_transition_notification(
    application_id: UUID,
    from_stage: str,
    to_stage: str,
    *,
    db: Session | None = None,
) -> None:
    """
    Notify candidate they completed one stage and moved to the next.
    No-op if from_stage == to_stage or stages are unchanged.

    Pass ``db`` only in tests; in production omit so a fresh session reads committed rows.
    """
    if from_stage == to_stage:
        return
    own_session = db is None
    sess = db if db is not None else SessionLocal()
    try:
        to_email, first_name = _load_candidate_email_and_name(sess, application_id)
    finally:
        if own_session:
            sess.close()
    if not to_email:
        return

    passed = _stage_label(from_stage)
    nxt = _stage_label(to_stage)
    title = "Ваша заявка переведена на следующий этап — inVision U"
    hi = f"Здравствуйте, {first_name}!" if first_name else "Здравствуйте!"
    body = [
        hi,
        f"Поздравляем: этап «{passed}» успешно пройден.",
        f"Ваша заявка переведена на следующий этап: «{nxt}».",
        "Следите за статусом в личном кабинете на платформе inVision U.",
    ]
    html_out = _wrap_html(body, title=title)
    send_html_email(to_email, title, html_out)


def send_revision_required_notification(application_id: UUID, *, db: Session | None = None) -> None:
    """Notify candidate that the application was returned for revision (not a forward stage pass)."""
    own_session = db is None
    sess = db if db is not None else SessionLocal()
    try:
        to_email, first_name = _load_candidate_email_and_name(sess, application_id)
    finally:
        if own_session:
            sess.close()
    if not to_email:
        return
    title = "Заявка возвращена на доработку — inVision U"
    hi = f"Здравствуйте, {first_name}!" if first_name else "Здравствуйте!"
    body = [
        hi,
        "Ваша заявка возвращена на этап заполнения: требуется доработка материалов.",
        "Откройте анкету в inVision U, внесите правки и отправьте заявку снова.",
    ]
    html_out = _wrap_html(body, title=title)
    send_html_email(to_email, title, html_out)


def send_final_decision_notification(
    application_id: UUID,
    final_decision_status: str,
    *,
    db: Session | None = None,
) -> None:
    """Notify candidate that a final admission outcome was recorded (stage remains «Результат»)."""
    own_session = db is None
    sess = db if db is not None else SessionLocal()
    try:
        to_email, first_name = _load_candidate_email_and_name(sess, application_id)
    finally:
        if own_session:
            sess.close()
    if not to_email:
        return
    label = FINAL_DECISION_LABEL_RU.get(final_decision_status, final_decision_status)
    title = "Итог по заявке — inVision U"
    hi = f"Здравствуйте, {first_name}!" if first_name else "Здравствуйте!"
    body = [
        hi,
        f"По вашей заявке зафиксирован итог: {label}.",
        "Подробности доступны в личном кабинете inVision U.",
    ]
    html_out = _wrap_html(body, title=title)
    send_html_email(to_email, title, html_out)
