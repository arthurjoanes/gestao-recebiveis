"""Saldo residual calculado dos recebimentos, sem cache financeiro."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import Subquery

from gestao_recebiveis.models import Payment, Receivable


@dataclass(frozen=True)
class Balance:
    paid_cents: int
    remaining_cents: int

    @property
    def payment_state(self) -> str:
        if self.remaining_cents == 0:
            return "paid"
        return "partial" if self.paid_cents else "unpaid"


def balance_from_paid(title: Receivable, paid_cents: int) -> Balance:
    if not 0 <= paid_cents <= title.amount_cents:
        raise RuntimeError(f"Saldo inconsistente no título {title.id}.")
    return Balance(paid_cents, title.amount_cents - paid_cents)


def get_balance(session: Session, title: Receivable) -> Balance:
    paid = session.scalar(
        select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(
            Payment.receivable_id == title.id
        )
    )
    return balance_from_paid(title, int(paid or 0))


def payment_totals() -> Subquery:
    """Uma linha por título; a soma bigint do PostgreSQL continua numeric exato."""
    return (
        select(
            Payment.receivable_id,
            func.sum(Payment.amount_cents).label("paid_cents"),
        )
        .group_by(Payment.receivable_id)
        .subquery("payment_totals")
    )


def expressions(totals: Subquery) -> tuple[ColumnElement[int], ColumnElement[int]]:
    paid = func.coalesce(totals.c.paid_cents, 0)
    return paid, Receivable.amount_cents - paid
