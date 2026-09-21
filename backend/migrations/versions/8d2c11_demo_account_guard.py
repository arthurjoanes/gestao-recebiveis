"""Mark local demonstration accounts explicitly."""

import sqlalchemy as sa
from alembic import op

revision = "8d2c11"
down_revision = "332fa6cea7a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    users = sa.table("users", sa.column("email"), sa.column("is_demo"))
    op.execute(
        users.update()
        .where(users.c.email.in_(["operador@example.com", "leitor@example.com"]))
        .values(is_demo=True)
    )


def downgrade() -> None:
    op.drop_column("users", "is_demo")
