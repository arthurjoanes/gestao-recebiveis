from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from gestao_recebiveis.clock import utcnow


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    password_hash: Mapped[str] = mapped_column(Text)
    __table_args__ = (CheckConstraint("role IN ('operator','reader')"),)


class LoginSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    csrf_token: Mapped[str] = mapped_column(String(100))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LoginAdmission(Base):
    __tablename__ = "login_admission"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer)
    __table_args__ = (Index("ix_login_admission_window_start", "window_start"),)


class DemoState(Base):
    __tablename__ = "demo_state"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    business_now: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    worker_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (CheckConstraint("id = 1"),)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_system: Mapped[str] = mapped_column(String(80))
    external_customer_id: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254))
    __table_args__ = (UniqueConstraint("source_system", "external_customer_id"),)


class Receivable(Base):
    __tablename__ = "receivables"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_system: Mapped[str] = mapped_column(String(80))
    external_receivable_id: Mapped[str] = mapped_column(String(100))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    description: Mapped[str] = mapped_column(String(500))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="open")
    scenario: Mapped[str] = mapped_column(String(30), default="success")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        UniqueConstraint("source_system", "external_receivable_id"),
        CheckConstraint("amount_cents > 0"),
        CheckConstraint("status IN ('open','paid','canceled')"),
        Index("ix_receivables_status_due", "status", "due_date"),
    )


class ImportBatch(Base):
    __tablename__ = "import_batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    content: Mapped[bytes] = mapped_column(LargeBinary)
    sha256: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="preview")
    report: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImportLine(Base):
    __tablename__ = "import_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"))
    line_number: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = (UniqueConstraint("batch_id", "line_number"),)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    receivable_id: Mapped[int] = mapped_column(ForeignKey("receivables.id"), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    note: Mapped[str] = mapped_column(String(500), default="")
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Reminder(Base):
    __tablename__ = "reminders"
    id: Mapped[int] = mapped_column(primary_key=True)
    receivable_id: Mapped[int] = mapped_column(ForeignKey("receivables.id"))
    stage: Mapped[int] = mapped_column(Integer)
    intent_business_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    attempts_count: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_error: Mapped[str | None] = mapped_column(String(500))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[int] = mapped_column(Integer, default=0)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        UniqueConstraint("receivable_id", "stage"),
        UniqueConstraint("receivable_id", "intent_business_date"),
        CheckConstraint("stage IN (-3,0,3,7)"),
        CheckConstraint(
            "status IN ('pending','processing','retry_scheduled','sent','failed','canceled','superseded')"
        ),
        Index("ix_reminders_claim", "status", "next_attempt_at"),
    )


class ReminderDayGuard(Base):
    __tablename__ = "reminder_day_guards"
    id: Mapped[int] = mapped_column(primary_key=True)
    receivable_id: Mapped[int] = mapped_column(ForeignKey("receivables.id"))
    business_date: Mapped[date] = mapped_column(Date)
    reminder_id: Mapped[int] = mapped_column(ForeignKey("reminders.id"))
    __table_args__ = (UniqueConstraint("receivable_id", "business_date"),)


class Attempt(Base):
    __tablename__ = "attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    reminder_id: Mapped[int] = mapped_column(ForeignKey("reminders.id"))
    number: Mapped[int] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(30), default="unknown")
    error: Mapped[str | None] = mapped_column(String(500))
    authorized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = (UniqueConstraint("reminder_id", "number"),)


class ProviderResult(Base):
    __tablename__ = "provider_results"
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id"), primary_key=True)
    outcome: Mapped[str] = mapped_column(String(30))
    error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Delivery(Base):
    __tablename__ = "deliveries"
    id: Mapped[int] = mapped_column(primary_key=True)
    reminder_id: Mapped[int] = mapped_column(ForeignKey("reminders.id"), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    message: Mapped[str] = mapped_column(Text)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    receivable_id: Mapped[int | None] = mapped_column(ForeignKey("receivables.id"))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(String(500))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    dedupe_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    business_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
