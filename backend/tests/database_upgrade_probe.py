"""Run only in a disposable *_test database, before provisioning any tables."""

import os
import subprocess

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from gestao_recebiveis.provision_database import main as provision


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
    subprocess.run(["alembic", "upgrade", "8d2c11"], env=legacy_env, check=True)
    subprocess.run(["python", "-m", "gestao_recebiveis.seed"], env=legacy_env, check=True)
    with admin.connect() as conn:
        before = conn.execute(
            text(
                "SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM customers), "
                "(SELECT count(*) FROM receivables), (SELECT sum(amount_cents) FROM payments)"
            )
        ).one()
    provision()
    provision()  # Existing roles and transferred objects: idempotent repeat.
    subprocess.run(["alembic", "upgrade", "head"], check=True)
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
        assert (
            conn.scalar(
                text(
                    "SELECT count(*) FROM pg_sequences WHERE schemaname='public' AND sequenceowner<>'gestao_owner'"
                )
            )
            == 0
        )
    # Reusing the runtime identity for the seed validates sequence and write grants.
    subprocess.run(["python", "-m", "gestao_recebiveis.seed"], check=True)
    print(
        "Upgrade passed: legacy 2 users, 60 customers, 240 receivables and payment totals preserved; roles idempotent."
    )


if __name__ == "__main__":
    main()
