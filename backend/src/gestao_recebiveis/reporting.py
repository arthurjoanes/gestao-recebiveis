from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, Integer, case, cast, func, literal, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from gestao_recebiveis.balances import expressions, payment_totals
from gestao_recebiveis.clock import business_now, utcnow
from gestao_recebiveis.errors import DomainError
from gestao_recebiveis.models import Customer, Payment, Receivable
from gestao_recebiveis.views import payment_view, title_view

AGING_BUCKETS = (
    ("current", "Em dia"),
    ("1_30", "1 a 30 dias"),
    ("31_60", "31 a 60 dias"),
    ("61_90", "61 a 90 dias"),
    ("over_90", "Acima de 90 dias"),
)


def aging_expression(today: date) -> ColumnElement[str]:
    days = cast(literal(today, type_=Date) - Receivable.due_date, Integer)
    return case(
        (days <= 0, "current"),
        (days <= 30, "1_30"),
        (days <= 60, "31_60"),
        (days <= 90, "61_90"),
        else_="over_90",
    )


def aging_bucket(due_date: date, today: date) -> str:
    days = (today - due_date).days
    if days <= 0:
        return "current"
    if days <= 30:
        return "1_30"
    if days <= 60:
        return "31_60"
    if days <= 90:
        return "61_90"
    return "over_90"


def search_filter(q: str) -> ColumnElement[bool]:
    escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return or_(
        Customer.name.ilike(f"%{escaped}%", escape="\\"),
        Receivable.external_receivable_id.ilike(f"%{escaped}%", escape="\\"),
        Receivable.description.ilike(f"%{escaped}%", escape="\\"),
    )


def title_filters(
    q: str,
    status: str | None,
    due_from: date | None,
    due_to: date | None,
    today: date,
    customer_id: int | None = None,
    bucket: str | None = None,
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if q:
        conditions.append(search_filter(q))
    if customer_id is not None:
        conditions.append(Receivable.customer_id == customer_id)
    if bucket is not None:
        if bucket not in dict(AGING_BUCKETS):
            raise DomainError("invalid_bucket", "Faixa de aging inválida.", 422)
        if status not in (None, "open"):
            raise DomainError("invalid_status", "A faixa de aging exige títulos abertos.", 422)
        conditions.extend([Receivable.status == "open", aging_expression(today) == bucket])
    if status == "overdue":
        conditions.extend([Receivable.status == "open", Receivable.due_date < today])
    elif status == "current":
        conditions.extend([Receivable.status == "open", Receivable.due_date >= today])
    elif status is not None:
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


def list_titles(
    session: Session,
    today: date,
    conditions: list[ColumnElement[bool]],
    page: int,
    page_size: int,
    *,
    include_aging: bool = False,
) -> dict[str, Any]:
    totals = payment_totals()
    paid, _ = expressions(totals)
    query = (
        select(Receivable, Customer, paid)
        .select_from(Receivable)
        .join(Customer, Receivable.customer_id == Customer.id)
        .outerjoin(totals, totals.c.receivable_id == Receivable.id)
        .where(*conditions)
    )
    count = session.scalar(select(func.count()).select_from(query.subquery()))
    rows = session.execute(
        query.order_by(Receivable.due_date, Receivable.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    title_ids = [title.id for title, _, _ in rows]
    payments_by_title: dict[int, list[dict[str, Any]]] = {title_id: [] for title_id in title_ids}
    if title_ids:
        for payment in session.scalars(
            select(Payment)
            .where(Payment.receivable_id.in_(title_ids))
            .order_by(Payment.paid_at, Payment.id)
        ):
            payments_by_title[payment.receivable_id].append(payment_view(payment))
    items = []
    for title, customer, paid_cents in rows:
        item = title_view(title, customer, today, int(paid_cents))
        item["payments"] = payments_by_title[title.id]
        if include_aging:
            item.update(
                aging_bucket=aging_bucket(title.due_date, today),
                days_overdue=max(0, (today - title.due_date).days),
            )
        items.append(item)
    return {"items": items, "total": count, "page": page, "page_size": page_size}


def received_period(
    today: date, received_from: date | None, received_to: date | None
) -> tuple[date, date]:
    start = received_from or today.replace(day=1)
    end = received_to or today
    if start > end:
        raise DomainError("invalid_period", "Período de recebimento inválido.", 422)
    return start, end


def payment_filters(
    q: str, start: date, end: date, customer_id: int | None = None
) -> list[ColumnElement[bool]]:
    # Vencimento/situação recortam títulos. Recebido no período consulta pagamentos
    # independentemente desses filtros e nunca altera o saldo atual do título.
    conditions = [
        cast(func.timezone("America/Sao_Paulo", Payment.paid_at), Date) >= start,
        cast(func.timezone("America/Sao_Paulo", Payment.paid_at), Date) <= end,
    ]
    if q:
        conditions.append(search_filter(q))
    if customer_id is not None:
        conditions.append(Receivable.customer_id == customer_id)
    return conditions


def report_metadata(commercial_now: datetime) -> dict[str, Any]:
    return {
        "generated_at": utcnow(),
        "business_now": commercial_now,
        "business_date": commercial_now.date(),
    }


def overview(
    session: Session,
    q: str,
    due_from: date | None,
    due_to: date | None,
    received_from: date | None,
    received_to: date | None,
) -> dict[str, Any]:
    commercial_now = business_now(session)
    today = commercial_now.date()
    start, end = received_period(today, received_from, received_to)
    conditions = title_filters(q, None, due_from, due_to, today)
    totals = payment_totals()
    _, remaining = expressions(totals)
    is_open = Receivable.status == "open"
    is_overdue = is_open & (Receivable.due_date < today)
    portfolio = session.execute(
        select(
            func.coalesce(func.sum(case((is_open, remaining), else_=0)), 0),
            func.coalesce(func.sum(case((is_overdue, remaining), else_=0)), 0),
            func.count().filter(is_open),
            func.count().filter(is_overdue),
            func.count().filter(Receivable.status == "canceled"),
        )
        .select_from(Receivable)
        .join(Customer, Customer.id == Receivable.customer_id)
        .outerjoin(totals, totals.c.receivable_id == Receivable.id)
        .where(*conditions)
    ).one()
    received = (
        select(func.coalesce(func.sum(Payment.amount_cents), 0), func.count(Payment.id))
        .select_from(Payment)
        .join(Receivable, Payment.receivable_id == Receivable.id)
        .join(Customer, Receivable.customer_id == Customer.id)
        .where(*payment_filters(q, start, end))
    )
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
        **report_metadata(commercial_now),
        "received_from": start,
        "received_to": end,
    }


def aging(
    session: Session,
    q: str,
    customer_id: int | None,
    due_from: date | None,
    due_to: date | None,
    bucket: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    commercial_now = business_now(session)
    today = commercial_now.date()
    conditions = title_filters(q, "open", due_from, due_to, today, customer_id, bucket)
    totals = payment_totals()
    _, remaining = expressions(totals)
    grouping = aging_expression(today)
    rows = session.execute(
        select(grouping, func.count(Receivable.id), func.coalesce(func.sum(remaining), 0))
        .select_from(Receivable)
        .join(Customer, Customer.id == Receivable.customer_id)
        .outerjoin(totals, totals.c.receivable_id == Receivable.id)
        .where(*conditions)
        .group_by(grouping)
    )
    observed = {key: (count, int(cents)) for key, count, cents in rows}
    buckets = [
        {
            "key": key,
            "label": label,
            "title_count": observed.get(key, (0, 0))[0],
            "remaining_cents": str(observed.get(key, (0, 0))[1]),
        }
        for key, label in AGING_BUCKETS
    ]
    return {
        **report_metadata(commercial_now),
        "q": q,
        "customer_id": customer_id,
        "due_from": due_from,
        "due_to": due_to,
        "bucket": bucket,
        "open_cents": str(sum(cents for _, cents in observed.values())),
        "title_count": sum(count for count, _ in observed.values()),
        "buckets": buckets,
        **list_titles(session, today, conditions, page, page_size, include_aging=True),
    }


def customer_statement(
    session: Session,
    customer_id: int,
    q: str,
    status: str | None,
    due_from: date | None,
    due_to: date | None,
    received_from: date | None,
    received_to: date | None,
    page: int,
    page_size: int,
    payment_page: int,
    payment_page_size: int,
) -> dict[str, Any]:
    commercial_now = business_now(session)
    today = commercial_now.date()
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise DomainError("not_found", "Cliente não encontrado.", 404)
    start, end = received_period(today, received_from, received_to)
    conditions = title_filters(q, status, due_from, due_to, today, customer_id)
    aggregates = payment_totals()
    paid, remaining = expressions(aggregates)
    amounts = session.execute(
        select(
            func.coalesce(func.sum(Receivable.amount_cents), 0),
            func.coalesce(func.sum(paid), 0),
            func.coalesce(func.sum(remaining), 0),
            func.coalesce(func.sum(case((Receivable.status == "open", remaining), else_=0)), 0),
            func.coalesce(func.sum(case((Receivable.status == "canceled", remaining), else_=0)), 0),
            func.count(Receivable.id),
        )
        .select_from(Receivable)
        .join(Customer, Customer.id == Receivable.customer_id)
        .outerjoin(aggregates, aggregates.c.receivable_id == Receivable.id)
        .where(*conditions)
    ).one()
    payment_conditions = payment_filters(q, start, end, customer_id)
    received_cents, paid_count = session.execute(
        select(func.coalesce(func.sum(Payment.amount_cents), 0), func.count(Payment.id))
        .select_from(Payment)
        .join(Receivable, Receivable.id == Payment.receivable_id)
        .join(Customer, Customer.id == Receivable.customer_id)
        .where(*payment_conditions)
    ).one()
    payment_rows = session.execute(
        select(Payment, Receivable)
        .join(Receivable, Receivable.id == Payment.receivable_id)
        .join(Customer, Customer.id == Receivable.customer_id)
        .where(*payment_conditions)
        .order_by(Payment.paid_at, Payment.id)
        .offset((payment_page - 1) * payment_page_size)
        .limit(payment_page_size)
    )
    payments = [
        {
            **payment_view(payment),
            "receivable_id": title.id,
            "source_system": title.source_system,
            "external_receivable_id": title.external_receivable_id,
            "note": payment.note,
        }
        for payment, title in payment_rows
    ]
    return {
        **report_metadata(commercial_now),
        "customer": {
            "id": customer.id,
            "source_system": customer.source_system,
            "external_customer_id": customer.external_customer_id,
            "name": customer.name,
            "email": customer.email,
        },
        "q": q,
        "status": status,
        "due_from": due_from,
        "due_to": due_to,
        "received_from": start,
        "received_to": end,
        "totals": {
            "amount_cents": str(amounts[0]),
            "paid_cents": str(amounts[1]),
            "remaining_cents": str(amounts[2]),
            "open_cents": str(amounts[3]),
            "canceled_remaining_cents": str(amounts[4]),
            "title_count": amounts[5],
            "received_cents": str(received_cents),
            "paid_count": paid_count,
        },
        "titles": list_titles(session, today, conditions, page, page_size),
        "payments": {
            "items": payments,
            "total": paid_count,
            "page": payment_page,
            "page_size": payment_page_size,
        },
    }
