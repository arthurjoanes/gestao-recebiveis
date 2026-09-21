from sqlalchemy import select
from sqlalchemy.orm import Session

from gestao_recebiveis.models import Attempt, Customer, Delivery, Receivable, Reminder


def reminder_view(
    session: Session, reminder: Reminder, *, detail: bool = False
) -> dict[str, object]:
    title = session.get(Receivable, reminder.receivable_id)
    if title is None:
        raise RuntimeError("Título do lembrete não encontrado.")
    customer = session.get(Customer, title.customer_id)
    if customer is None:
        raise RuntimeError("Cliente do título não encontrado.")
    result: dict[str, object] = {
        "id": reminder.id,
        "receivable_id": reminder.receivable_id,
        "external_receivable_id": title.external_receivable_id,
        "customer_name": customer.name,
        "amount_cents": str(title.amount_cents),
        "stage": reminder.stage,
        "status": reminder.status,
        "attempts_count": reminder.attempts_count,
        "next_attempt_at": reminder.next_attempt_at,
        "last_error": reminder.last_error,
        "lease_expires_at": reminder.lease_expires_at,
        "idempotency_key": reminder.idempotency_key,
        "cancel_requested": reminder.cancel_requested,
        "intent_business_date": reminder.intent_business_date,
    }
    if detail:
        attempts = session.scalars(
            select(Attempt).where(Attempt.reminder_id == reminder.id).order_by(Attempt.number)
        ).all()
        result["attempts"] = [
            {
                "id": attempt.id,
                "number": attempt.number,
                "outcome": attempt.outcome,
                "error": attempt.error,
                "authorized_at": attempt.authorized_at,
                "finished_at": attempt.finished_at,
            }
            for attempt in attempts
        ]
        delivery = session.scalar(select(Delivery).where(Delivery.reminder_id == reminder.id))
        result["delivery"] = (
            {
                "id": delivery.id,
                "accepted_at": delivery.accepted_at,
                "message": delivery.message,
            }
            if delivery is not None
            else None
        )
    return result
