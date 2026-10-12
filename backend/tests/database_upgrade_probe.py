"""Run only in a disposable *_test database, before provisioning any tables."""

import os
import subprocess
import sys

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gestao_recebiveis.balances import get_balance
from gestao_recebiveis.models import Payment, Receivable
from gestao_recebiveis.provision_database import main as provision
from gestao_recebiveis.receivables import pay


def main() -> None:
    admin_url = os.environ["DATABASE_ADMIN_URL"]
    database = make_url(admin_url).database
    if not database or not database.endswith("_test"):
        raise SystemExit("Upgrade probe requires a disposable *_test database.")
    admin = create_engine(admin_url)
    with admin.connect() as conn:
        if conn.scalar(text("SELECT to_regclass('public.users')")):
            raise SystemExit("Upgrade probe requires an empty database; existing data left intact.")
    legacy_env = {**os.environ, "DATABASE_URL": admin_url, "MIGRATION_DATABASE_URL": admin_url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "8d2c11"], env=legacy_env, check=True
    )
    subprocess.run([sys.executable, "-m", "gestao_recebiveis.seed"], env=legacy_env, check=True)
    with admin.connect() as conn:
        before = conn.execute(
            text(
                "SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM customers), "
                "(SELECT count(*) FROM receivables), (SELECT sum(amount_cents) FROM payments)"
            )
        ).one()
        legacy_payments = conn.execute(text("SELECT * FROM payments ORDER BY id")).all()
        assert len(legacy_payments) == 48
    provision()
    provision()  # Existing roles and transferred objects: idempotent repeat.
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "d6420a"], check=True)
    # This inconsistency exists only in the disposable fixture. The migration
    # must diagnose it, preserving both the bad fixture and the previous revision.
    with admin.begin() as conn:
        original = conn.execute(
            text("SELECT id, amount_cents FROM payments ORDER BY id LIMIT 1")
        ).one()
        conn.execute(text("UPDATE payments SET amount_cents=0 WHERE id=:id"), {"id": original.id})
    refused = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert refused.returncode != 0 and "Migração financeira recusada" in refused.stderr
    with admin.begin() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "d6420a"
        assert (
            conn.scalar(text("SELECT amount_cents FROM payments WHERE id=:id"), {"id": original.id})
            == 0
        )
        conn.execute(
            text("UPDATE payments SET amount_cents=:amount WHERE id=:id"),
            {"id": original.id, "amount": original.amount_cents},
        )
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    provision()  # Post-migration repeat must preserve the restricted version table.
    runtime = create_engine(os.environ["DATABASE_URL"])
    with runtime.connect() as conn:
        after = conn.execute(
            text(
                "SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM customers), "
                "(SELECT count(*) FROM receivables), (SELECT sum(amount_cents) FROM payments)"
            )
        ).one()
        assert before == after
        assert conn.execute(text("SELECT * FROM payments ORDER BY id")).all() == legacy_payments
        assert tuple(after[:3]) == (2, 60, 240)
        assert conn.scalar(text("SELECT current_user")) == "gestao_app"
        assert conn.scalar(text("SELECT has_table_privilege(current_user, 'users', 'INSERT')"))
        assert not conn.scalar(
            text("SELECT has_table_privilege(current_user, 'alembic_version', 'UPDATE')")
        )
        assert (
            conn.scalar(
                text(
                    "SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner<>'gestao_owner'"
                )
            )
            == 0
        )
    inspector = inspect(runtime)
    assert {
        tuple(foreign_key["constrained_columns"])
        for foreign_key in inspector.get_foreign_keys("payments")
    } == {("receivable_id",), ("actor_id",)}
    assert not any(
        constraint["column_names"] == ["receivable_id"]
        for constraint in inspector.get_unique_constraints("payments")
    )
    assert any(
        constraint["column_names"] == ["idempotency_key"]
        for constraint in inspector.get_unique_constraints("payments")
    )
    assert any(
        index["name"] == "ix_payments_receivable_paid"
        for index in inspector.get_indexes("payments")
    )
    assert any(
        check["name"] == "ck_payments_amount_positive"
        for check in inspector.get_check_constraints("payments")
    )
    # A legacy-only database can return safely to the legacy schema. This also
    # proves that downgrade does not rewrite any immutable receipt field.
    subprocess.run([sys.executable, "-m", "alembic", "downgrade", "d6420a"], check=True)
    with runtime.connect() as conn:
        assert conn.execute(text("SELECT * FROM payments ORDER BY id")).all() == legacy_payments
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    with Session(runtime) as session, session.begin():
        legacy = session.scalars(select(Payment).order_by(Payment.id)).first()
        assert legacy is not None
        replay = pay(
            session, legacy.receivable_id, legacy.idempotency_key, legacy.note, legacy.actor_id
        )
        assert replay.id == legacy.id and replay.request_hash == legacy.request_hash
        title = session.scalars(
            select(Receivable).where(Receivable.status == "open").order_by(Receivable.id)
        ).first()
        assert title is not None and title.amount_cents > 2
        partial = pay(
            session,
            title.id,
            "upgrade-probe-first-partial",
            "Parcela sintética",
            legacy.actor_id,
            "1",
        )
        pay(
            session,
            title.id,
            "upgrade-probe-second-partial",
            "Parcela sintética",
            legacy.actor_id,
            "1",
        )
        assert partial.amount_cents == 1 and title.status == "open"
        assert get_balance(session, title).paid_cents == 2
    with runtime.connect() as conn:
        multiple_snapshot = conn.execute(text("SELECT * FROM payments ORDER BY id")).all()
    refused_downgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "d6420a"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert refused_downgrade.returncode != 0 and "Downgrade recusado" in refused_downgrade.stderr
    with runtime.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "e71c2f"
        assert conn.execute(text("SELECT * FROM payments ORDER BY id")).all() == multiple_snapshot
    with runtime.begin() as conn:
        try:
            with conn.begin_nested():
                conn.execute(
                    text("UPDATE payments SET amount_cents=0 WHERE id=:id"), {"id": original.id}
                )
        except IntegrityError:
            pass
        else:
            raise AssertionError("CHECK must refuse zero receipts.")
        assert (
            conn.scalar(
                text(
                    "SELECT count(*) FROM pg_sequences WHERE schemaname='public' AND sequenceowner<>'gestao_owner'"
                )
            )
            == 0
        )
    # Reusing the runtime identity for the seed validates sequence and write grants.
    subprocess.run([sys.executable, "-m", "gestao_recebiveis.seed"], check=True)
    print(
        "Upgrade passed: legacy IDs, timestamps, hashes and 48 receipts preserved and replayed; "
        "partial receipts supported, inconsistent upgrade and destructive downgrade refused; roles idempotent."
    )


if __name__ == "__main__":
    main()
