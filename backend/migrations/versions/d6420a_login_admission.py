"""Persist short-lived login admission counters."""

import sqlalchemy as sa
from alembic import op

revision = "d6420a"
down_revision = "8d2c11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_admission",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )

    op.create_index("ix_login_admission_window_start", "login_admission", ["window_start"])


def downgrade() -> None:
    op.drop_table("login_admission")
