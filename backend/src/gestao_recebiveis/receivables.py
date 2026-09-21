import hashlib
import json

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from gestao_recebiveis.audit import record
from gestao_recebiveis.clock import business_now
from gestao_recebiveis.errors import DomainError
from gestao_recebiveis.models import Payment, Receivable
from gestao_recebiveis.reminders.service import cancel_pending


def locked_title(session: Session, receivable_id: int) -> Receivable:
    title = session.scalar(
        select(Receivable)
        .where(Receivable.id == receivable_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if title is None:
        raise DomainError("not_found", "Título não encontrado.", 404)
    return title


def pay(session: Session, receivable_id: int, key: str, note: str, actor_id: int) -> Payment:
    digest = hashlib.sha256(
        json.dumps({"receivable_id": receivable_id, "note": note}, sort_keys=True).encode()
    ).hexdigest()
    # Serialize equal idempotency keys even when they target different titles.
    lock_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})
    previous = session.scalar(select(Payment).where(Payment.idempotency_key == key))
    if previous:
        if previous.request_hash != digest:
            raise DomainError(
                "idempotency_conflict", "Chave de pagamento já usada com outro conteúdo."
            )
        return previous
    title = locked_title(session, receivable_id)
    if title.status != "open":
        raise DomainError("invalid_transition", "Somente títulos em aberto aceitam baixa.")
    payment = Payment(
        receivable_id=title.id,
        idempotency_key=key,
        request_hash=digest,
        amount_cents=title.amount_cents,
        note=note,
        actor_id=actor_id,
        paid_at=business_now(session),
    )
    session.add(payment)
    title.status = "paid"
    cancel_pending(session, title.id, "Título pago.")
    record(
        session,
        "payment_recorded",
        "Pagamento integral registrado.",
        title.id,
        actor_id,
        {"amount_cents": str(title.amount_cents), "note": note},
    )
    session.flush()
    return payment


def cancel(session: Session, receivable_id: int, reason: str, actor_id: int) -> Receivable:
    title = locked_title(session, receivable_id)
    if title.status == "canceled":
        return title
    if title.status != "open":
        raise DomainError("invalid_transition", "Título pago não pode ser cancelado.")
    title.status = "canceled"
    cancel_pending(session, title.id, "Título cancelado.")
    record(
        session, "receivable_canceled", "Título cancelado.", title.id, actor_id, {"reason": reason}
    )
    return title
