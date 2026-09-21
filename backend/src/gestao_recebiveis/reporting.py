from datetime import date
from typing import Any

from sqlalchemy import Date, case, cast, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from gestao_recebiveis.clock import business_date
from gestao_recebiveis.errors import DomainError
from gestao_recebiveis.models import Customer, Payment, Receivable


def search_filter(q: str) -> ColumnElement[bool]:
    escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return or_(
        Customer.name.ilike(f"%{escaped}%", escape="\\"),
        Receivable.external_receivable_id.ilike(f"%{escaped}%", escape="\\"),
        Receivable.description.ilike(f"%{escaped}%", escape="\\"),
    )


def title_filters(
    q: str, status: str | None, due_from: date | None, due_to: date | None, today: date
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if q:
        conditions.append(search_filter(q))
    if status == "overdue":
        conditions.extend([Receivable.status == "open", Receivable.due_date < today])
    elif status == "current":
        conditions.extend([Receivable.status == "open", Receivable.due_date >= today])
    elif status:
        if status not in ("open", "paid", "canceled"):
            raise DomainError("invalid_status", "Situação de título inválida.", 422)
        conditions.append(Receivable.status == status)
    if due_from:
        conditions.append(Receivable.due_date >= due_from)
    if due_to:
        conditions.append(Receivable.due_date <= due_to)
    if due_from and due_to and due_from > due_to:
        raise DomainError(
            "invalid_period", "A data inicial deve ser anterior ou igual à final.", 422
        )
    return conditions


def overview(
    session: Session,
    q: str,
    due_from: date | None,
    due_to: date | None,
    received_from: date | None,
    received_to: date | None,
) -> dict[str, Any]:
    today = business_date(session)
    start = received_from or today.replace(day=1)
    end = received_to or today
    if start > end:
        raise DomainError("invalid_period", "Período de recebimento inválido.", 422)
    conditions = title_filters(q, None, due_from, due_to, today)
    is_open = Receivable.status == "open"
    is_overdue = is_open & (Receivable.due_date < today)
    portfolio = session.execute(
        select(
            func.coalesce(func.sum(case((is_open, Receivable.amount_cents), else_=0)), 0),
            func.coalesce(func.sum(case((is_overdue, Receivable.amount_cents), else_=0)), 0),
            func.count().filter(is_open),
            func.count().filter(is_overdue),
            func.count().filter(Receivable.status == "canceled"),
        )
        .join(Customer, Customer.id == Receivable.customer_id)
        .where(*conditions)
    ).one()
    received = (
        select(func.coalesce(func.sum(Payment.amount_cents), 0), func.count(Payment.id))
        .select_from(Payment)
        .join(Receivable, Payment.receivable_id == Receivable.id)
        .join(Customer, Receivable.customer_id == Customer.id)
        .where(
            cast(func.timezone("America/Sao_Paulo", Payment.paid_at), Date) >= start,
            cast(func.timezone("America/Sao_Paulo", Payment.paid_at), Date) <= end,
        )
    )
    if q:
        received = received.where(search_filter(q))
    paid_sum, paid_count = session.execute(received).one()
    return {
        "open_cents": str(portfolio[0]),
        "overdue_cents": str(portfolio[1]),
        "current_cents": str(portfolio[0] - portfolio[1]),
        "current_count": portfolio[2] - portfolio[3],
        "open_count": portfolio[2],
        "overdue_count": portfolio[3],
        "canceled_count": portfolio[4],
        "received_cents": str(paid_sum),
        "paid_count": paid_count,
        "business_date": today,
        "received_from": start,
        "received_to": end,
    }
