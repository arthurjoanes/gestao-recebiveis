from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, Path, Query, Request, Response, UploadFile
from sqlalchemy import func, select

from gestao_recebiveis import imports, receivables, reporting
from gestao_recebiveis.audit import record
from gestao_recebiveis.auth import (
    CurrentUser,
    Db,
    Operator,
    authenticate,
    check_origin,
    create_login,
)
from gestao_recebiveis.clock import business_date, business_now
from gestao_recebiveis.config import get_settings
from gestao_recebiveis.errors import DomainError
from gestao_recebiveis.import_csv import MAX_BYTES
from gestao_recebiveis.models import (
    Attempt,
    Customer,
    DemoState,
    ImportBatch,
    Receivable,
    Reminder,
    User,
)
from gestao_recebiveis.reminders.views import reminder_view
from gestao_recebiveis.responses import (
    AuthResponse,
    DemoResponse,
    ImportBatchResponse,
    ImportBatchSummaryResponse,
    LogoutResponse,
    OverviewResponse,
    PaymentResponse,
    ReceivableDetailResponse,
    ReceivableResponse,
    ReminderDetailResponse,
    ReminderResponse,
)
from gestao_recebiveis.responses import Page as PageResponse
from gestao_recebiveis.schemas import (
    CancelInput,
    ClockInput,
    LoginInput,
    PaymentInput,
    ScenarioInput,
    WorkerInput,
)
from gestao_recebiveis.views import batch_view, payment_view, title_detail, title_view

router = APIRouter(prefix="/api/v1")
ResourceId = Annotated[int, Path(ge=1, le=2147483647)]
Page = Annotated[int, Query(ge=1, le=10_000)]
PageSize = Annotated[int, Query(ge=1, le=100)]
Search = Annotated[str, Query(max_length=200)]
ReminderStatus = Literal[
    "pending", "processing", "retry_scheduled", "sent", "failed", "canceled", "superseded"
]


def session_view(user: User, csrf: str) -> dict[str, Any]:
    return {
        "user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role},
        "csrf_token": csrf,
    }


@router.post("/auth/login", response_model=AuthResponse)
def login(body: LoginInput, request: Request, response: Response, session: Db) -> dict[str, Any]:
    check_origin(request)
    user = authenticate(session, body.email, body.password)
    token, login_session = create_login(session, user)
    settings = get_settings()
    response.set_cookie(
        "cf_session",
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_hours * 3600,
        path="/",
    )
    return session_view(user, login_session.csrf_token)


@router.get("/auth/session", response_model=AuthResponse)
def auth_session(request: Request, user: CurrentUser) -> dict[str, Any]:
    return session_view(user, request.state.login.csrf_token)


@router.post("/auth/logout", response_model=LogoutResponse)
def logout(request: Request, response: Response, session: Db, user: CurrentUser) -> dict[str, bool]:
    session.delete(request.state.login)
    response.delete_cookie(
        "cf_session", path="/", secure=get_settings().cookie_secure, httponly=True, samesite="lax"
    )
    return {"ok": True}


@router.get("/receivables", response_model=PageResponse[ReceivableResponse])
def titles(
    session: Db,
    user: CurrentUser,
    q: Search = "",
    status: str | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    page: Page = 1,
    page_size: PageSize = 20,
) -> dict[str, Any]:
    today = business_date(session)
    conditions = reporting.title_filters(q, status, due_from, due_to, today)
    query = (
        select(Receivable, Customer)
        .join(Customer, Receivable.customer_id == Customer.id)
        .where(*conditions)
    )
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    rows = session.execute(
        query.order_by(Receivable.due_date, Receivable.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {
        "items": [title_view(title, customer, today) for title, customer in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/receivables/{receivable_id}", response_model=ReceivableDetailResponse)
def title(receivable_id: ResourceId, session: Db, user: CurrentUser) -> dict[str, Any]:
    item = session.get(Receivable, receivable_id)
    if not item:
        raise DomainError("not_found", "Título não encontrado.", 404)
    return title_detail(session, item)


@router.post("/receivables/{receivable_id}/payments", response_model=PaymentResponse)
def pay(
    receivable_id: ResourceId, body: PaymentInput, session: Db, user: Operator
) -> dict[str, Any]:
    return payment_view(
        receivables.pay(session, receivable_id, body.idempotency_key, body.note, user.id)
    )


@router.post("/receivables/{receivable_id}/cancel", response_model=ReceivableDetailResponse)
def cancel(
    receivable_id: ResourceId, body: CancelInput, session: Db, user: Operator
) -> dict[str, Any]:
    item = receivables.cancel(session, receivable_id, body.reason, user.id)
    session.flush()
    return title_detail(session, item)


@router.get("/overview", response_model=OverviewResponse)
def overview(
    session: Db,
    user: CurrentUser,
    q: Search = "",
    due_from: date | None = None,
    due_to: date | None = None,
    received_from: date | None = None,
    received_to: date | None = None,
) -> dict[str, Any]:
    return reporting.overview(session, q, due_from, due_to, received_from, received_to)


@router.post("/imports", response_model=ImportBatchResponse)
def preview(session: Db, user: Operator, file: Annotated[UploadFile, File()]) -> dict[str, Any]:
    return batch_view(
        imports.create_preview(
            session, file.filename or "arquivo.csv", file.file.read(MAX_BYTES + 1), user.id
        )
    )


@router.get("/imports", response_model=PageResponse[ImportBatchSummaryResponse])
def batches(
    session: Db, user: CurrentUser, page: Page = 1, page_size: PageSize = 20
) -> dict[str, Any]:
    items = session.execute(
        select(
            ImportBatch.id,
            ImportBatch.filename,
            ImportBatch.status,
            ImportBatch.created_at,
            ImportBatch.report["row_count"].as_integer().label("row_count"),
        )
        .order_by(ImportBatch.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {
        "items": [dict(item._mapping) for item in items],
        "total": session.scalar(select(func.count(ImportBatch.id))),
        "page": page,
        "page_size": page_size,
    }


@router.get("/imports/{batch_id}", response_model=ImportBatchResponse)
def batch(batch_id: ResourceId, session: Db, user: CurrentUser) -> dict[str, Any]:
    item = session.get(ImportBatch, batch_id)
    if not item:
        raise DomainError("not_found", "Lote não encontrado.", 404)
    return batch_view(item)


@router.post("/imports/{batch_id}/confirm", response_model=ImportBatchResponse)
def confirm(batch_id: ResourceId, session: Db, user: Operator) -> dict[str, Any]:
    return batch_view(imports.confirm_batch(session, batch_id, user.id))


@router.get("/reminders", response_model=PageResponse[ReminderResponse])
def reminders(
    session: Db,
    user: CurrentUser,
    status: ReminderStatus | None = None,
    q: Search = "",
    page: Page = 1,
    page_size: PageSize = 20,
) -> dict[str, Any]:
    query = (
        select(Reminder)
        .join(Receivable, Receivable.id == Reminder.receivable_id)
        .join(Customer, Customer.id == Receivable.customer_id)
    )
    if status:
        query = query.where(Reminder.status == status)
    if q:
        query = query.where(reporting.search_filter(q))
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    jobs = session.scalars(
        query.order_by(Reminder.id.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return {
        "items": [reminder_view(session, job) for job in jobs],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/reminders/{reminder_id}", response_model=ReminderDetailResponse)
def reminder(reminder_id: ResourceId, session: Db, user: CurrentUser) -> dict[str, Any]:
    job = session.get(Reminder, reminder_id)
    if not job:
        raise DomainError("not_found", "Lembrete não encontrado.", 404)
    return reminder_view(session, job, detail=True)


def demo_state(session: Db) -> dict[str, Any]:
    state = session.get(DemoState, 1)
    return {
        "enabled": get_settings().demo_mode,
        "business_now": business_now(session),
        "business_date": business_date(session),
        "worker_enabled": state.worker_enabled if state else True,
        "policy": "D−3, D0, D+3 e D+7 às 09:00. Até um lembrete por título e dia. Envio simulado.",
    }


def require_demo() -> None:
    if not get_settings().demo_mode:
        raise DomainError("demo_disabled", "Controles disponíveis apenas no modo demo.", 403)


@router.get("/demo", response_model=DemoResponse)
def demo(session: Db, user: CurrentUser) -> dict[str, Any]:
    return demo_state(session)


@router.post("/demo/clock", response_model=DemoResponse)
def advance_clock(body: ClockInput, session: Db, user: Operator) -> dict[str, Any]:
    require_demo()
    if not 1900 <= body.business_now.year <= 2199:
        raise DomainError(
            "invalid_clock", "O relógio de demonstração aceita anos de 1900 a 2199.", 422
        )
    state = session.scalar(select(DemoState).where(DemoState.id == 1).with_for_update())
    if state is None:
        raise DomainError("demo_not_seeded", "Execute o seed de demonstração.", 409)
    if body.business_now.tzinfo is None or body.business_now <= state.business_now:
        raise DomainError(
            "invalid_clock",
            "Informe data e hora com fuso, posteriores ao relógio comercial atual.",
            422,
        )
    state.business_now = body.business_now
    record(
        session,
        "demo_clock_advanced",
        "Relógio comercial avançado.",
        actor_id=user.id,
        details={"business_now": body.business_now.isoformat()},
    )
    return demo_state(session)


@router.post("/demo/worker", response_model=DemoResponse)
def set_worker(body: WorkerInput, session: Db, user: Operator) -> dict[str, Any]:
    require_demo()
    state = session.get(DemoState, 1)
    if not state:
        raise DomainError("demo_not_seeded", "Execute o seed de demonstração.")
    state.worker_enabled = body.enabled
    record(
        session,
        "demo_worker_changed",
        "Processamento retomado."
        if body.enabled
        else "Processamento pausado; autorizações anteriores podem concluir.",
        actor_id=user.id,
    )
    return demo_state(session)


@router.post("/demo/scenario", response_model=ReceivableDetailResponse)
def set_scenario(body: ScenarioInput, session: Db, user: Operator) -> dict[str, Any]:
    require_demo()
    item = receivables.locked_title(session, body.receivable_id)
    count = session.scalar(
        select(func.count(Attempt.id))
        .join(Reminder, Reminder.id == Attempt.reminder_id)
        .where(Reminder.receivable_id == item.id)
    )
    if count or item.status != "open":
        raise DomainError(
            "scenario_locked",
            "Escolha o cenário em um título aberto antes da primeira autorização.",
        )
    item.scenario = body.scenario
    record(
        session,
        "demo_scenario_changed",
        "Cenário configurado.",
        item.id,
        user.id,
        {"scenario": body.scenario},
    )
    return title_detail(session, item)
