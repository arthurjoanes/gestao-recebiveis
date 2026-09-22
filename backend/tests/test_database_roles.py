import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from gestao_recebiveis.database import engine


def test_runtime_database_is_not_administrator() -> None:
    if "MIGRATION_DATABASE_URL" not in os.environ:
        pytest.skip("Legacy standalone probe; Compose test exercises isolated runtime roles.")
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT current_user, rolsuper, rolcreatedb, rolcreaterole, rolbypassrls "
                "FROM pg_roles WHERE rolname=current_user"
            )
        ).one()
        assert tuple(row) == ("gestao_app", False, False, False, False)


@pytest.mark.parametrize(
    "statement",
    [
        "CREATE TABLE public.forbidden_runtime_ddl (id integer)",
        "ALTER TABLE users ADD COLUMN forbidden_runtime_column integer",
        "UPDATE alembic_version SET version_num='forbidden'",
        "SET ROLE gestao_owner",
        "CREATE ROLE forbidden_runtime_role",
    ],
)
def test_runtime_cannot_change_schema_or_roles(statement: str) -> None:
    if "MIGRATION_DATABASE_URL" not in os.environ:
        pytest.skip("Legacy standalone probe; Compose test exercises isolated runtime roles.")
    with engine.connect() as connection:
        with pytest.raises(DBAPIError) as error:
            connection.execute(text(statement))
        assert error.value.orig.sqlstate == "42501"  # type: ignore[union-attr]
        connection.rollback()
