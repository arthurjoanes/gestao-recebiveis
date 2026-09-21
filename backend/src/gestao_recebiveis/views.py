from datetime import UTC, date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gestao_recebiveis.clock import business_date
from gestao_recebiveis.models import AuditEvent, Customer, ImportBatch, Payment, Receivable, Reminder


def payment_view(payment: Payment) -> dict[str, Any]:
    return {
        "id": payment.id,
        "amount_cents": str(payment.amount_cents),
        "paid_at": payment.paid_at.astimezone(UTC),
        "recorded_at": payment.recorded_at,
    }


def title_view(title: Receivable, customer: Customer, today: date) -> dict[str, Any]:
    return {
        "id": title.id,
        "source_system": title.source_system,
        "external_receivable_id": title.external_receivable_id,
        "customer_id": customer.id,
        "customer_name": customer.name,
        "customer_email": customer.email,
        "description": title.description,
        "amount_cents": str(title.amount_cents),
        "due_date": title.due_date,
        "status": title.status,
        "overdue": title.status == "open" and title.due_date < today,
        "scenario": title.scenario,
    }


def title_detail(session: Session, title: Receivable) -> dict[str, Any]:
    from gestao_recebiveis.reminders.views import reminder_view

    customer = session.get(Customer, title.customer_id)
    assert customer is not None
    result = title_view(title, customer, business_date(session))
    payment = session.scalar(select(Payment).where(Payment.receivable_id == title.id))
    result["payment"] = payment_view(payment) if payment else None
    result["reminders"] = [
        reminder_view(session, job, detail=True)
        for job in session.scalars(
            select(Reminder).where(Reminder.receivable_id == title.id).order_by(Reminder.id.desc())
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
            select(AuditEvent)
            .where(AuditEvent.receivable_id == title.id)
            .order_by(AuditEvent.id.desc())
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
