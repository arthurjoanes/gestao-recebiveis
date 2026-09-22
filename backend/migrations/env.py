import os

from alembic import context
from sqlalchemy import create_engine, pool, text

from gestao_recebiveis.config import get_settings
from gestao_recebiveis.models import Base

config = context.config
target_metadata = Base.metadata

if context.is_offline_mode():
    context.configure(
        url=os.environ.get("MIGRATION_DATABASE_URL", get_settings().database_url),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(
        os.environ.get("MIGRATION_DATABASE_URL", get_settings().database_url),
        poolclass=pool.NullPool,
    )
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()

        # Runtime can inspect readiness, but cannot forge the migration version.
        with connection.begin():
            if connection.scalar(text("SELECT 1 FROM pg_roles WHERE rolname='gestao_app'")):
                connection.execute(
                    text("REVOKE INSERT, UPDATE, DELETE ON alembic_version FROM gestao_app")
                )
                connection.execute(text("GRANT SELECT ON alembic_version TO gestao_app"))
