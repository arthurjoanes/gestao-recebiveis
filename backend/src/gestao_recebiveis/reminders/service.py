from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from gestao_recebiveis.audit import record
from gestao_recebiveis.clock import Clock, SystemClock, business_now
from gestao_recebiveis.config import get_settings
from gestao_recebiveis.models import Attempt, Customer, Receivable, Reminder, ReminderDayGuard
from gestao_recebiveis.reminders.policy import eligible_stages, retry_delay
from gestao_recebiveis.reminders.provider import SendResult

ACTIVE_STATUSES = ("pending", "processing", "retry_scheduled")


@dataclass(frozen=True)
class Claim:
    reminder_id: int
    receivable_id: int
    token: int


def _latest_attempt(session: Session, reminder_id: int) -> Attempt | None:
    return session.scalar(
        select(Attempt)
        .where(Attempt.reminder_id == reminder_id)
        .order_by(Attempt.number.desc())
        .limit(1)
        .execution_options(populate_existing=True)
    )


def _reserve_day(session: Session, job: Reminder, day: date) -> bool:
    session.execute(
        insert(ReminderDayGuard)
        .values(receivable_id=job.receivable_id, business_date=day, reminder_id=job.id)
        .on_conflict_do_nothing(index_elements=["receivable_id", "business_date"])
    )
    owner = session.scalar(
        select(ReminderDayGuard.reminder_id).where(
            ReminderDayGuard.receivable_id == job.receivable_id,
            ReminderDayGuard.business_date == day,
        )
    )
    return owner == job.id


def _end_without_send(session: Session, job: Reminder, status: str, reason: str) -> None:
    job.status = status
    job.last_error = reason
    job.lease_expires_at = None
    record(
        session,
        f"reminder.{status}",
        reason,
        job.receivable_id,
        details={"reminder_id": job.id, "stage": job.stage},
        dedupe_key=f"reminder:{job.id}:{status}",
    )


def _load_scheduling_jobs(
    session: Session, title_ids: list[int]
) -> tuple[dict[int, list[Reminder]], dict[int, Attempt]]:
    """Carrega jobs e últimas tentativas; títulos já estão bloqueados pelo chamador."""
    jobs_by_title: dict[int, list[Reminder]] = defaultdict(list)
    jobs = (
        session.scalars(
            select(Reminder)
            .where(Reminder.receivable_id.in_(title_ids))
            .order_by(Reminder.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).all()
        if title_ids
        else []
    )
    for job in jobs:
        jobs_by_title[job.receivable_id].append(job)
    active_with_attempts = [
        job.id for job in jobs if job.status in ACTIVE_STATUSES and job.attempts_count > 0
    ]
    previous_attempts = (
        {
            attempt.reminder_id: attempt
            for attempt in session.scalars(
                select(Attempt)
                .where(Attempt.reminder_id.in_(active_with_attempts))
                .distinct(Attempt.reminder_id)
                .order_by(Attempt.reminder_id, Attempt.number.desc())
                .execution_options(populate_existing=True)
            )
        }
        if active_with_attempts
        else {}
    )
    return jobs_by_title, previous_attempts


def schedule(session: Session, *, clock: Clock | None = None) -> int:
    """Agenda dentro da transação do chamador; lock de título precede jobs."""
    now = (clock or SystemClock()).now()
    commercial_now = business_now(session)
    day = commercial_now.date()
    latest_due_date = date.fromordinal(min(day.toordinal() + 3, date.max.toordinal()))
    titles = session.scalars(
        select(Receivable)
        .where(Receivable.status == "open", Receivable.due_date <= latest_due_date)
        .order_by(Receivable.id)
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    ).all()
    jobs_by_title, previous_attempts = _load_scheduling_jobs(
        session, [title.id for title in titles]
    )
    created = 0
    for title in titles:
        stages = eligible_stages(title.due_date, commercial_now)
        if not stages:
            continue
        latest = stages[-1]
        jobs = jobs_by_title[title.id]
        blocked = False
        for job in jobs:
            if job.status not in ACTIVE_STATUSES:
                continue
            previous = previous_attempts.get(job.id)
            uncertain = previous is not None and previous.outcome == "unknown"
            expired_without_authorization = (
                job.status == "processing"
                and not uncertain
                and (job.lease_expires_at is None or job.lease_expires_at <= now)
            )
            if expired_without_authorization and job.stage < latest:
                _end_without_send(
                    session,
                    job,
                    "superseded",
                    "Lease expirado antes da autorização; etapa encerrada.",
                )
                continue
            if job.status == "processing" or uncertain:
                # Reconciliar um trabalho antigo ocupa o dia atual, mesmo que a
                # intenção tenha sido criada antes. Isso evita rajada após restart.
                _reserve_day(session, job, day)
                blocked = True
            elif job.stage < latest:
                _end_without_send(
                    session,
                    job,
                    "superseded",
                    "Etapa ultrapassada antes da confirmação da entrega.",
                )
        if blocked:
            continue
        existing_stages = {job.stage for job in jobs}
        if latest in existing_stages:
            continue
        for stage in stages[:-1]:
            if stage not in existing_stages:
                record(
                    session,
                    "reminder.stage_skipped",
                    "Etapa antiga substituída pela mais recente.",
                    title.id,
                    details={"stage": stage, "selected_stage": latest},
                    dedupe_key=f"receivable:{title.id}:stage:{stage}:skipped",
                )
        day_used = session.scalar(
            select(ReminderDayGuard.id).where(
                ReminderDayGuard.receivable_id == title.id,
                ReminderDayGuard.business_date == day,
            )
        )
        if day_used is not None:
            continue
        job = Reminder(
            receivable_id=title.id,
            stage=latest,
            intent_business_date=day,
            status="pending",
            idempotency_key=f"cf:{title.id}:stage:{latest}",
            attempts_count=0,
            next_attempt_at=now,
            lease_token=0,
            cancel_requested=False,
            created_at=now,
        )
        session.add(job)
        session.flush()
        _reserve_day(session, job, day)
        record(
            session,
            "reminder.scheduled",
            "Lembrete agendado.",
            title.id,
            details={"reminder_id": job.id, "stage": latest},
            dedupe_key=f"reminder:{job.id}:scheduled",
        )
        created += 1
    return created


def claim(session: Session, *, clock: Clock | None = None) -> Claim | None:
    """A transação deve terminar antes de authorize adquirir o lock do título."""
    now = (clock or SystemClock()).now()
    job = session.scalar(
        select(Reminder)
        .where(
            or_(
                and_(
                    Reminder.status.in_(("pending", "retry_scheduled")),
                    Reminder.next_attempt_at <= now,
                ),
                and_(
                    Reminder.status == "processing",
                    or_(Reminder.lease_expires_at <= now, Reminder.lease_expires_at.is_(None)),
                ),
            )
        )
        .order_by(Reminder.next_attempt_at, Reminder.id)
        .with_for_update(skip_locked=True)
        .limit(1)
        .execution_options(populate_existing=True)
    )
    if job is None:
        return None
    job.status = "processing"
    job.lease_token += 1
    job.lease_expires_at = now + timedelta(seconds=get_settings().lease_seconds)
    return Claim(job.id, job.receivable_id, job.lease_token)


def _owned(job: Reminder | None, possession: Claim, clock: Clock) -> bool:
    return (
        job is not None
        and job.status == "processing"
        and job.lease_token == possession.token
        and job.lease_expires_at is not None
        and job.lease_expires_at > clock.now()
    )


def authorize(session: Session, possession: Claim, *, clock: Clock | None = None) -> Attempt | None:
    infra_clock = clock or SystemClock()
    title = session.scalar(
        select(Receivable)
        .where(Receivable.id == possession.receivable_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    job = session.scalar(
        select(Reminder)
        .where(Reminder.id == possession.reminder_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if title is None or job is None or not _owned(job, possession, infra_clock):
        return None
    previous = _latest_attempt(session, job.id)
    if previous is not None and previous.outcome == "unknown":
        _reserve_day(session, job, business_now(session).date())
        record(
            session,
            "reminder.reconciling",
            "Resposta desconhecida. Consultando a mesma tentativa.",
            title.id,
            details={"reminder_id": job.id, "attempt_id": previous.id, "token": possession.token},
            dedupe_key=f"reminder:{job.id}:reconcile:{possession.token}",
        )
        return previous
    if title.status != "open" or job.cancel_requested:
        _end_without_send(session, job, "canceled", "Título encerrado; envio bloqueado.")
        return None
    stages = eligible_stages(title.due_date, business_now(session))
    if stages and stages[-1] > job.stage:
        _end_without_send(
            session, job, "superseded", "Etapa ultrapassada antes da autorização de envio."
        )
        return None
    if job.attempts_count >= get_settings().max_attempts:
        _end_without_send(session, job, "failed", "Limite de tentativas atingido.")
        return None
    if not _reserve_day(session, job, business_now(session).date()):
        _end_without_send(session, job, "superseded", "Outro lembrete já ocupa o dia comercial.")
        return None
    customer = session.get(Customer, title.customer_id)
    if customer is None:
        raise RuntimeError("Cliente do título não encontrado.")
    job.attempts_count += 1
    attempt = Attempt(
        reminder_id=job.id,
        number=job.attempts_count,
        outcome="unknown",
        authorized_at=infra_clock.now(),
        payload={
            "idempotency_key": job.idempotency_key,
            "scenario": title.scenario,
            "receivable_id": title.id,
            "external_receivable_id": title.external_receivable_id,
            "amount_cents": str(title.amount_cents),
            "due_date": title.due_date.isoformat(),
            "stage": job.stage,
            "customer_email": customer.email,
            "message": (
                f"[SIMULAÇÃO — nenhuma mensagem externa] Olá, {customer.name}. "
                f"Lembrete do título {title.external_receivable_id}, "
                f"vencimento {title.due_date.isoformat()}, "
                f"valor R$ {title.amount_cents // 100},{title.amount_cents % 100:02d}."
            ),
        },
    )
    session.add(attempt)
    session.flush()
    record(
        session,
        "reminder.authorized",
        "Envio autorizado; pode estar em trânsito.",
        title.id,
        details={"reminder_id": job.id, "attempt_id": attempt.id, "number": attempt.number},
        dedupe_key=f"attempt:{attempt.id}:authorized",
    )
    return attempt


def renew(session: Session, possession: Claim, *, clock: Clock | None = None) -> bool:
    now = (clock or SystemClock()).now()
    result = session.execute(
        update(Reminder)
        .where(
            Reminder.id == possession.reminder_id,
            Reminder.lease_token == possession.token,
            Reminder.status == "processing",
            Reminder.lease_expires_at > now,
        )
        .values(lease_expires_at=now + timedelta(seconds=get_settings().lease_seconds))
        .returning(Reminder.id)
    )
    return result.scalar_one_or_none() is not None


def finish(
    session: Session,
    possession: Claim,
    attempt_id: int,
    result: SendResult,
    *,
    clock: Clock | None = None,
) -> bool:
    if result.outcome not in {"unknown", "success", "transient", "permanent"}:
        raise ValueError("Resultado de provedor inválido.")
    infra_clock = clock or SystemClock()
    title = session.scalar(
        select(Receivable)
        .where(Receivable.id == possession.receivable_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    job = session.scalar(
        select(Reminder)
        .where(Reminder.id == possession.reminder_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if title is None or job is None or not _owned(job, possession, infra_clock):
        return False
    attempt = session.get(Attempt, attempt_id, populate_existing=True)
    if attempt is None or attempt.reminder_id != job.id or attempt.outcome != "unknown":
        return False
    job.lease_expires_at = None
    job.last_error = result.error
    settings = get_settings()
    delay_scale = settings.demo_retry_base_seconds if settings.demo_mode else 1.0
    if result.outcome == "unknown":
        job.status = "retry_scheduled"
        job.next_attempt_at = infra_clock.now() + timedelta(
            seconds=retry_delay(1, demo=settings.demo_mode) * delay_scale
        )
        attempt.error = result.error
        record(
            session,
            "reminder.result_unknown",
            "Sem resposta. Consultar a tentativa autorizada.",
            title.id,
            details={"reminder_id": job.id, "attempt_id": attempt.id},
            dedupe_key=f"attempt:{attempt.id}:unknown:{possession.token}",
        )
        return True
    attempt.outcome = result.outcome
    attempt.error = result.error
    attempt.finished_at = infra_clock.now()
    if result.outcome == "success":
        job.status = "sent"
        message = "Entrega simulada confirmada."
    elif result.outcome == "permanent":
        job.status = "failed"
        message = "Falha permanente; tentativa não será repetida."
    elif title.status != "open" or job.cancel_requested:
        job.status = "canceled"
        message = "Sem entrega. Título encerrado; retry bloqueado."
    elif job.attempts_count >= settings.max_attempts:
        job.status = "failed"
        message = "Limite de tentativas atingido após falhas transitórias."
    else:
        job.status = "retry_scheduled"
        job.next_attempt_at = infra_clock.now() + timedelta(
            seconds=retry_delay(attempt.number, demo=settings.demo_mode) * delay_scale
        )
        message = "Falha transitória sem entrega. Retry agendado."
    record(
        session,
        f"reminder.{job.status}",
        message,
        title.id,
        details={"reminder_id": job.id, "attempt_id": attempt.id, "outcome": result.outcome},
        dedupe_key=f"attempt:{attempt.id}:finished",
    )
    return True


def cancel_pending(session: Session, receivable_id: int, reason: str) -> None:
    """O chamador deve já possuir o lock do título; esta função não faz commit."""
    jobs = session.scalars(
        select(Reminder)
        .where(Reminder.receivable_id == receivable_id, Reminder.status.in_(ACTIVE_STATUSES))
        .order_by(Reminder.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    for job in jobs:
        previous = _latest_attempt(session, job.id)
        job.cancel_requested = True
        if previous is not None and previous.outcome == "unknown":
            record(
                session,
                "reminder.cancel_requested",
                "Título encerrado; consultando a tentativa autorizada.",
                receivable_id,
                details={"reminder_id": job.id, "reason": reason},
                dedupe_key=f"reminder:{job.id}:cancel_requested",
            )
        else:
            _end_without_send(session, job, "canceled", reason)
