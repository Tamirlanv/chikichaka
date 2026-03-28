from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.application import AuditLog


def write_audit(
    db: Session,
    *,
    entity_type: str,
    entity_id: UUID,
    action: str,
    actor_user_id: UUID | None = None,
    before_data: dict[str, Any] | None = None,
    after_data: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    row = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_user_id=actor_user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        before_data=before_data,
        after_data=after_data,
        created_at=datetime.now(tz=UTC),
    )
    db.add(row)
    db.flush()
    return row
