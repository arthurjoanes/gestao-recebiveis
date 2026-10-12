"""Allow multiple positive receipts while preserving legacy financial data."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e71c2f"
down_revision: str | None = "d6420a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _lock_and_validate() -> None:
    connection = op.get_bind()
    # Match the title -> payment order used by financial writers, and prevent
    # changes between validation and the constraint changes.
    connection.execute(sa.text("LOCK TABLE receivables IN ACCESS EXCLUSIVE MODE"))
    connection.execute(sa.text("LOCK TABLE payments IN ACCESS EXCLUSIVE MODE"))
    invalid = connection.execute(
        sa.text(
            "SELECT r.id, r.status, r.amount_cents, COALESCE(p.paid_cents, 0) AS paid_cents "
            "FROM receivables r LEFT JOIN ("
            "SELECT receivable_id, sum(amount_cents) AS paid_cents, "
            "bool_and(amount_cents > 0) AS positive FROM payments GROUP BY receivable_id"
            ") p ON p.receivable_id = r.id "
            "WHERE r.amount_cents <= 0 OR p.positive = false "
            "OR COALESCE(p.paid_cents, 0) > r.amount_cents "
            "OR (r.status = 'paid' AND COALESCE(p.paid_cents, 0) <> r.amount_cents) "
            "OR (r.status = 'open' AND COALESCE(p.paid_cents, 0) >= r.amount_cents) "
            "OR (r.status = 'canceled' AND COALESCE(p.paid_cents, 0) <> 0) "
            "ORDER BY r.id LIMIT 1"
        )
    ).first()
    if invalid is not None:
        raise RuntimeError(
            f"Migração financeira recusada: título {invalid.id}, status {invalid.status}, "
            f"original {invalid.amount_cents}, recebido {invalid.paid_cents}; "
            "corrija a inconsistência na origem sem alterar dinheiro silenciosamente."
        )


def upgrade() -> None:
    _lock_and_validate()
    invalid_legacy = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT p.id, p.receivable_id FROM payments p "
                "JOIN receivables r ON r.id=p.receivable_id "
                "WHERE p.amount_cents <> r.amount_cents OR r.status <> 'paid' "
                "ORDER BY p.id LIMIT 1"
            )
        )
        .first()
    )
    if invalid_legacy is not None:
        raise RuntimeError(
            f"Migração financeira recusada: pagamento legado {invalid_legacy.id} do título "
            f"{invalid_legacy.receivable_id} não corresponde à quitação integral legada."
        )
    constraints = [
        constraint
        for constraint in sa.inspect(op.get_bind()).get_unique_constraints("payments")
        if constraint["column_names"] == ["receivable_id"]
    ]
    if len(constraints) != 1 or not constraints[0]["name"]:
        raise RuntimeError("Unicidade legada de payments.receivable_id não identificada.")
    op.drop_constraint(constraints[0]["name"], "payments", type_="unique")
    op.create_index("ix_payments_receivable_paid", "payments", ["receivable_id", "paid_at", "id"])
    op.create_check_constraint("ck_payments_amount_positive", "payments", "amount_cents > 0")


def downgrade() -> None:
    _lock_and_validate()
    incompatible = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT p.receivable_id FROM payments p JOIN receivables r ON r.id=p.receivable_id "
                "GROUP BY p.receivable_id, r.amount_cents "
                "HAVING count(*) > 1 OR sum(p.amount_cents) <> r.amount_cents "
                "ORDER BY p.receivable_id LIMIT 1"
            )
        )
        .scalar_one_or_none()
    )
    if incompatible is not None:
        raise RuntimeError(
            f"Downgrade recusado: título {incompatible} possui múltiplos recebimentos "
            "ou pagamento parcial incompatível com o contrato legado; nenhum pagamento foi apagado."
        )
    op.create_unique_constraint("payments_receivable_id_key", "payments", ["receivable_id"])
    op.drop_constraint("ck_payments_amount_positive", "payments", type_="check")
    op.drop_index("ix_payments_receivable_paid", table_name="payments")
