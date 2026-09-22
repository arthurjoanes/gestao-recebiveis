"""Idempotently provision this application's owner and runtime roles.

Only the one-shot db-init container receives the bootstrap administrator URL.
Existing application tables are transferred individually; data is never reset.
"""

import os

from sqlalchemy import create_engine, text

from gestao_recebiveis.models import Base

OWNER = "gestao_owner"
RUNTIME = "gestao_app"


def main() -> None:
    engine = create_engine(os.environ["DATABASE_ADMIN_URL"])
    owner_password = os.environ["DATABASE_OWNER_PASSWORD"]
    app_password = os.environ["DATABASE_APP_PASSWORD"]
    if min(len(owner_password), len(app_password)) < 24 or owner_password == app_password:
        raise ValueError("Use senhas distintas com pelo menos 24 caracteres para owner e app.")
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(83471022)"))
        # quote_literal handles arbitrary passwords without string interpolation.
        for role, password in ((OWNER, owner_password), (RUNTIME, app_password)):
            if not conn.scalar(text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role}):
                conn.exec_driver_sql(f"CREATE ROLE {role}")
            quoted = conn.scalar(text("SELECT quote_literal(:value)"), {"value": password})
            conn.exec_driver_sql(
                f"ALTER ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                f"NOREPLICATION NOBYPASSRLS NOINHERIT PASSWORD {quoted}"
            )
        conn.exec_driver_sql(f"REVOKE {OWNER} FROM {RUNTIME}")
        conn.exec_driver_sql("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        conn.exec_driver_sql(f"ALTER SCHEMA public OWNER TO {OWNER}")
        conn.exec_driver_sql(f"REVOKE ALL ON SCHEMA public FROM {RUNTIME}")
        conn.exec_driver_sql(f"GRANT USAGE ON SCHEMA public TO {RUNTIME}")
        database = conn.scalar(text("SELECT quote_ident(current_database())"))
        conn.exec_driver_sql(f"REVOKE CREATE, TEMPORARY ON DATABASE {database} FROM PUBLIC")
        conn.exec_driver_sql(f"GRANT CONNECT ON DATABASE {database} TO {OWNER}, {RUNTIME}")
        names = [*Base.metadata.tables, "alembic_version"]
        for name in names:
            # These identifiers come exclusively from local SQLAlchemy metadata.
            if conn.scalar(text("SELECT to_regclass(:name)"), {"name": f"public.{name}"}):
                conn.exec_driver_sql(f'ALTER TABLE public."{name}" OWNER TO {OWNER}')
                conn.exec_driver_sql(f'REVOKE ALL ON public."{name}" FROM {RUNTIME}')
                privileges = (
                    "SELECT" if name == "alembic_version" else "SELECT, INSERT, UPDATE, DELETE"
                )
                conn.exec_driver_sql(f'GRANT {privileges} ON public."{name}" TO {RUNTIME}')
        # SERIAL sequences linked to transferred tables follow their owner's role.
        conn.exec_driver_sql(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {RUNTIME}")
        conn.exec_driver_sql(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE {OWNER} IN SCHEMA public "
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {RUNTIME}"
        )
        conn.exec_driver_sql(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE {OWNER} IN SCHEMA public "
            f"GRANT USAGE, SELECT ON SEQUENCES TO {RUNTIME}"
        )
    engine.dispose()
    print("Database roles ready; existing application data preserved.")


if __name__ == "__main__":
    main()
