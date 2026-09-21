"""initial_schema"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "332fa6cea7a1"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_system", sa.String(length=80), nullable=False),
        sa.Column("external_customer_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_system", "external_customer_id"),
    )
    op.create_table(
        "demo_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_now", sa.DateTime(timezone=True), nullable=False),
        sa.Column("worker_enabled", sa.Boolean(), nullable=False),
        sa.CheckConstraint("id = 1"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.CheckConstraint("role IN ('operator','reader')"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "receivables",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_system", sa.String(length=80), nullable=False),
        sa.Column("external_receivable_id", sa.String(length=100), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("scenario", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('open','paid','canceled')"),
        sa.CheckConstraint("amount_cents > 0"),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_system", "external_receivable_id"),
    )
    op.create_index(
        "ix_receivables_status_due", "receivables", ["status", "due_date"], unique=False
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("csrf_token", sa.String(length=100), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("receivable_id", sa.Integer(), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("dedupe_key", sa.String(length=200), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("business_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["receivable_id"],
            ["receivables.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_table(
        "import_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "line_number"),
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("receivable_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["receivable_id"],
            ["receivables.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("receivable_id"),
    )
    op.create_table(
        "reminders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("receivable_id", sa.Integer(), nullable=False),
        sa.Column("stage", sa.Integer(), nullable=False),
        sa.Column("intent_business_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("attempts_count", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_token", sa.Integer(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','processing','retry_scheduled','sent','failed','canceled','superseded')"
        ),
        sa.CheckConstraint("stage IN (-3,0,3,7)"),
        sa.ForeignKeyConstraint(
            ["receivable_id"],
            ["receivables.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("receivable_id", "intent_business_date"),
        sa.UniqueConstraint("receivable_id", "stage"),
    )
    op.create_index("ix_reminders_claim", "reminders", ["status", "next_attempt_at"], unique=False)
    op.create_table(
        "attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reminder_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["reminder_id"],
            ["reminders.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reminder_id", "number"),
    )
    op.create_table(
        "deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reminder_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["reminder_id"],
            ["reminders.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("reminder_id"),
    )
    op.create_table(
        "reminder_day_guards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("receivable_id", sa.Integer(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("reminder_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["receivable_id"],
            ["receivables.id"],
        ),
        sa.ForeignKeyConstraint(
            ["reminder_id"],
            ["reminders.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receivable_id", "business_date"),
    )
    op.create_table(
        "provider_results",
        sa.Column("attempt_id", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["attempts.id"],
        ),
        sa.PrimaryKeyConstraint("attempt_id"),
    )


def downgrade() -> None:
    op.drop_table("provider_results")
    op.drop_table("reminder_day_guards")
    op.drop_table("deliveries")
    op.drop_table("attempts")
    op.drop_index("ix_reminders_claim", table_name="reminders")
    op.drop_table("reminders")
    op.drop_table("payments")
    op.drop_table("import_lines")
    op.drop_table("audit_events")
    op.drop_table("sessions")
    op.drop_index("ix_receivables_status_due", table_name="receivables")
    op.drop_table("receivables")
    op.drop_table("import_batches")
    op.drop_table("users")
    op.drop_table("demo_state")
    op.drop_table("customers")
