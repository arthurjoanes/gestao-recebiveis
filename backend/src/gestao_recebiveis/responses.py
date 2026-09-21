from datetime import date
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, Field, JsonValue

Cents = Annotated[
    str,
    Field(
        pattern=r"^(0|[1-9][0-9]*)$",
        description="Centavos inteiros não negativos, enviados como string para preservar precisão.",
        examples=["125009"],
    ),
]


class UserResponse(BaseModel):
    id: int = Field(gt=0)
    email: str
    name: str
    role: Literal["operator", "reader"]


class AuthResponse(BaseModel):
    user: UserResponse
    csrf_token: str


class LogoutResponse(BaseModel):
    ok: Literal[True]


class PaymentResponse(BaseModel):
    id: int = Field(gt=0)
    amount_cents: Cents
    paid_at: AwareDatetime
    recorded_at: AwareDatetime


class ReceivableResponse(BaseModel):
    id: int = Field(gt=0)
    source_system: str
    external_receivable_id: str
    customer_id: int = Field(gt=0)
    customer_name: str
    customer_email: str
    description: str
    amount_cents: Cents
    due_date: date
    status: Literal["open", "paid", "canceled"]
    overdue: bool
    scenario: Literal["success", "transient", "permanent", "response_lost", "always_transient"]


class AttemptResponse(BaseModel):
    id: int = Field(gt=0)
    number: int = Field(ge=1)
    outcome: Literal["unknown", "success", "transient", "permanent"]
    error: str | None
    authorized_at: AwareDatetime
    finished_at: AwareDatetime | None


class DeliveryResponse(BaseModel):
    id: int = Field(gt=0)
    accepted_at: AwareDatetime
    message: str


class ReminderResponse(BaseModel):
    id: int = Field(gt=0)
    receivable_id: int = Field(gt=0)
    external_receivable_id: str
    customer_name: str
    amount_cents: Cents
    stage: Literal[-3, 0, 3, 7]
    status: Literal[
        "pending", "processing", "retry_scheduled", "sent", "failed", "canceled", "superseded"
    ]
    attempts_count: int = Field(ge=0)
    next_attempt_at: AwareDatetime
    last_error: str | None
    lease_expires_at: AwareDatetime | None
    idempotency_key: str
    cancel_requested: bool
    intent_business_date: date


class ReminderDetailResponse(ReminderResponse):
    attempts: list[AttemptResponse]
    delivery: DeliveryResponse | None


class AuditEventResponse(BaseModel):
    id: int = Field(gt=0)
    type: str
    message: str
    occurred_at: AwareDatetime
    business_at: AwareDatetime
    details: dict[str, JsonValue]


class ReceivableDetailResponse(ReceivableResponse):
    payment: PaymentResponse | None
    reminders: list[ReminderDetailResponse]
    events: list[AuditEventResponse]


class ImportErrorResponse(BaseModel):
    line: int = Field(
        ge=0, description="Linha informada no relatório; zero indica erro do arquivo."
    )
    code: str
    message: str


class ImportLineResponse(BaseModel):
    line: int = Field(ge=1)
    external_receivable_id: str
    customer_name: str
    amount_cents: Cents
    due_date: date
    status: Literal["new", "existing", "duplicate", "conflict", "invalid", "blocked"]
    message: str = ""


class ImportReportResponse(BaseModel):
    row_count: int = Field(ge=0)
    new_count: int = Field(ge=0)
    existing_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    total_cents: Cents
    errors: list[ImportErrorResponse]
    rows: list[ImportLineResponse]


class ImportBatchResponse(BaseModel):
    id: int = Field(gt=0)
    filename: str
    status: Literal["preview", "confirmed", "rejected"]
    created_at: AwareDatetime
    report: ImportReportResponse


class ImportBatchSummaryResponse(BaseModel):
    id: int = Field(gt=0)
    filename: str
    status: Literal["preview", "confirmed", "rejected"]
    created_at: AwareDatetime
    row_count: int = Field(ge=0)


class DemoResponse(BaseModel):
    enabled: bool
    business_now: AwareDatetime
    business_date: date
    worker_enabled: bool
    policy: str


class OverviewResponse(BaseModel):
    current_cents: Cents
    current_count: int = Field(ge=0)
    open_cents: Cents
    overdue_cents: Cents
    received_cents: Cents
    open_count: int = Field(ge=0)
    overdue_count: int = Field(ge=0)
    paid_count: int = Field(ge=0)
    canceled_count: int = Field(ge=0)
    business_date: date
    received_from: date
    received_to: date


class Page[T](BaseModel):
    items: list[T]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
