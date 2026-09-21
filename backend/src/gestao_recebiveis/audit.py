from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from gestao_recebiveis.clock import business_now, utcnow
from gestao_recebiveis.models import AuditEvent


def record(
    session: Session,
    event_type: str,
    message: str,
    receivable_id: int | None = None,
    actor_id: int | None = None,
    details: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
) -> None:
    session.execute(
        insert(AuditEvent)
        .values(
            type=event_type,
            message=message,
            receivable_id=receivable_id,
            actor_id=actor_id,
            details=details or {},
            dedupe_key=dedupe_key,
            occurred_at=utcnow(),
            business_at=business_now(session),
        )
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
    )
