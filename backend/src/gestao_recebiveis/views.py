from datetime import UTC, date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gestao_recebiveis.balances import balance_from_paid
from gestao_recebiveis.clock import business_date
from gestao_recebiveis.models import (
    AuditEvent,
    Customer,
    ImportBatch,
    Payment,
    Receivable,
    Reminder,
)


def payment_view(payment: Payment) -> dict[str, Any]:
    return {
        "id": payment.id,
        "amount_cents": str(payment.amount_cents),
        "paid_at": payment.paid_at.astimezone(UTC),
        "recorded_at": payment.recorded_at,
        "note": payment.note,
    }


def title_view(
    title: Receivable, customer: Customer, today: date, paid_cents: int
) -> dict[str, Any]:
    balance = balance_from_paid(title, paid_cents)
    return {
        "id": title.id,
        "source_system": title.source_system,
        "external_receivable_id": title.external_receivable_id,
        "customer_id": customer.id,
        "customer_name": customer.name,
        "customer_email": customer.email,
        "description": title.description,
        "amount_cents": str(title.amount_cents),
        "paid_cents": str(balance.paid_cents),
        "remaining_cents": str(balance.remaining_cents),
        "payment_state": balance.payment_state,
        "due_date": title.due_date,
        "status": title.status,
        "overdue": title.status == "open" and title.due_date < today,
        "scenario": title.scenario,
    }


def title_detail(
    session: Session,
    title: Receivable,
    *,
    page_size: int | None = None,
    payment_page: int = 1,
    event_page: int = 1,
    reminder_page: int = 1,
) -> dict[str, Any]:
    from gestao_recebiveis.reminders.views import reminder_view

    customer = session.get(Customer, title.customer_id)
    assert customer is not None
    paid, payment_count = session.execute(
        select(func.coalesce(func.sum(Payment.amount_cents), 0), func.count(Payment.id)).where(
            Payment.receivable_id == title.id
        )
    ).one()

    def bounded(query: Any, page: int) -> Any:
        return query.offset((page - 1) * page_size).limit(page_size) if page_size else query

    payments = session.scalars(
        bounded(
            select(Payment)
            .where(Payment.receivable_id == title.id)
            .order_by(Payment.paid_at, Payment.id),
            payment_page,
        )
    ).all()
    result = title_view(title, customer, business_date(session), int(paid))
    result["payments"] = [payment_view(payment) for payment in payments]
    only_payment = (
        session.scalar(select(Payment).where(Payment.receivable_id == title.id))
        if payment_count == 1
        else None
    )
    result["payment"] = payment_view(only_payment) if only_payment else None
    if page_size:
        result["history"] = {
            "payments": {"total": payment_count, "page": payment_page, "page_size": page_size},
            "events": {
                "total": session.scalar(
                    select(func.count(AuditEvent.id)).where(AuditEvent.receivable_id == title.id)
                ),
                "page": event_page,
                "page_size": page_size,
            },
            "reminders": {
                "total": session.scalar(
                    select(func.count(Reminder.id)).where(Reminder.receivable_id == title.id)
                ),
                "page": reminder_page,
                "page_size": page_size,
            },
        }
    result["reminders"] = [
        reminder_view(session, job, detail=True, paid_cents=paid, title=title, customer=customer)
        for job in session.scalars(
            bounded(
                select(Reminder)
                .where(Reminder.receivable_id == title.id)
                .order_by(Reminder.id if page_size else Reminder.id.desc()),
                reminder_page,
            )
        )
    ]
    result["events"] = [
        {
            "id": event.id,
            "type": event.type,
            "message": event.message,
            "occurred_at": event.occurred_at,
            "business_at": event.business_at,
            "details": event.details,
        }
        for event in session.scalars(
            bounded(
                select(AuditEvent)
                .where(AuditEvent.receivable_id == title.id)
                .order_by(AuditEvent.id if page_size else AuditEvent.id.desc()),
                event_page,
            )
        )
    ]
    return result


def batch_view(batch: ImportBatch) -> dict[str, Any]:
    return {
        "id": batch.id,
        "filename": batch.filename,
        "status": batch.status,
        "created_at": batch.created_at,
        "report": batch.report,
    }
