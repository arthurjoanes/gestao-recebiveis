from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from threading import Barrier

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from gestao_recebiveis.clock import BUSINESS_TZ, FixedClock
from gestao_recebiveis.config import get_settings
from gestao_recebiveis.models import (
    Attempt,
    AuditEvent,
    Customer,
    Delivery,
    DemoState,
    ProviderResult,
    Receivable,
    Reminder,
    ReminderDayGuard,
)
from gestao_recebiveis.receivables import pay
from gestao_recebiveis.reminders.policy import eligible_stages
from gestao_recebiveis.reminders.provider import FakeProvider, ResponseLost, SendResult
from gestao_recebiveis.reminders.service import (
    Claim,
    authorize,
    claim,
    finish,
    renew,
    schedule,
)
from gestao_recebiveis.worker import run_once


@pytest.fixture
def infrastructure_clock() -> FixedClock:
    return FixedClock(datetime(2026, 9, 1, 12, tzinfo=UTC))


@pytest.fixture(autouse=True)
def reminder_environment(
    db: Session, session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "demo_mode", True)
    with session_factory.begin() as session:
        state = session.get(DemoState, 1)
        if state is None:
            session.add(
                DemoState(
                    id=1,
                    business_now=datetime(2026, 8, 17, 10, tzinfo=BUSINESS_TZ),
                    worker_enabled=True,
                )
            )
        else:
            state.business_now = datetime(2026, 8, 17, 10, tzinfo=BUSINESS_TZ)
            state.worker_enabled = True


def create_title(
    factory: sessionmaker[Session],
    *,
    scenario: str = "success",
    due: date = date(2026, 8, 20),
) -> int:
    with factory.begin() as session:
        customer = Customer(
            source_system="reminder-tests",
            external_customer_id="C1",
            name="Cliente Fictício",
            email="cliente@example.com",
        )
        session.add(customer)
        session.flush()
        title = Receivable(
            source_system="reminder-tests",
            external_receivable_id="T1",
            customer_id=customer.id,
            description="Venda fictícia",
            amount_cents=12345,
            due_date=due,
            status="open",
            scenario=scenario,
        )
        session.add(title)
        session.flush()
        return title.id


def set_business_time(factory: sessionmaker[Session], instant: datetime) -> None:
    with factory.begin() as session:
        state = session.get(DemoState, 1)
        assert state is not None
        state.business_now = instant


def take_job(factory: sessionmaker[Session], clock: FixedClock) -> tuple[Claim, int]:
    with factory.begin() as session:
        possession = claim(session, clock=clock)
        assert possession is not None
    with factory.begin() as session:
        attempt = authorize(session, possession, clock=clock)
        assert attempt is not None
        return possession, attempt.id


def job_state(factory: sessionmaker[Session]) -> tuple[str, int]:
    with factory() as session:
        job = session.scalars(select(Reminder).order_by(Reminder.id.desc())).first()
        assert job is not None
        return job.status, job.attempts_count


def test_policy_target_hour_and_final_stage() -> None:
    due = date(2026, 8, 20)
    assert eligible_stages(due, datetime(2026, 8, 17, 8, 59, tzinfo=BUSINESS_TZ)) == ()
    assert eligible_stages(due, datetime(2026, 8, 17, 9, tzinfo=BUSINESS_TZ)) == (-3,)
    assert eligible_stages(due, datetime(2026, 8, 20, 8, 59, tzinfo=BUSINESS_TZ)) == (-3,)
    assert eligible_stages(due, datetime(2026, 8, 20, 9, tzinfo=BUSINESS_TZ)) == (-3, 0)
    assert eligible_stages(due, datetime(2026, 9, 20, 9, tzinfo=BUSINESS_TZ)) == (-3, 0, 3, 7)


@pytest.mark.parametrize(
    "due,now,expected",
    [
        (date.min, datetime(1, 1, 1, 8, 59, tzinfo=BUSINESS_TZ), (-3,)),
        (date.min, datetime(1, 1, 1, 9, tzinfo=BUSINESS_TZ), (-3, 0)),
        (date.min, datetime(2026, 8, 17, 10, tzinfo=BUSINESS_TZ), (-3, 0, 3, 7)),
        (date.max, datetime(2026, 8, 17, 10, tzinfo=BUSINESS_TZ), ()),
        (date.max, datetime(9999, 12, 31, 8, 59, tzinfo=BUSINESS_TZ), (-3,)),
        (date.max, datetime(9999, 12, 31, 9, tzinfo=BUSINESS_TZ), (-3, 0)),
    ],
)
def test_policy_accepts_extreme_iso_dates_without_overflow(
    due: date, now: datetime, expected: tuple[int, ...]
) -> None:
    assert eligible_stages(due, now) == expected


@pytest.mark.parametrize(
    "due,now,expected_stage",
    [
        (date.min, datetime(2026, 8, 17, 10, tzinfo=BUSINESS_TZ), 7),
        (date.max, datetime(2026, 8, 17, 10, tzinfo=BUSINESS_TZ), None),
        (date.max, datetime(9999, 12, 30, 10, tzinfo=BUSINESS_TZ), -3),
        (date.max, datetime(9999, 12, 31, 10, tzinfo=BUSINESS_TZ), 0),
    ],
)
def test_worker_processes_extreme_due_dates_and_clamps_horizon(
    session_factory: sessionmaker[Session],
    infrastructure_clock: FixedClock,
    due: date,
    now: datetime,
    expected_stage: int | None,
) -> None:
    create_title(session_factory, due=due)
    set_business_time(session_factory, now)
    assert run_once(session_factory, clock=infrastructure_clock) == (expected_stage is not None)
    with session_factory() as session:
        job = session.scalar(select(Reminder))
        if expected_stage is None:
            assert job is None
        else:
            assert job is not None and job.stage == expected_stage and job.status == "sent"
        assert session.scalar(select(func.count(Delivery.id))) == (expected_stage is not None)


def test_repeated_and_concurrent_schedule_has_one_intention(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    create_title(session_factory)
    start = Barrier(2)
    hold_transaction = Barrier(2)

    def schedule_concurrently() -> int:
        with session_factory.begin() as session:
            start.wait(timeout=10)
            created = schedule(session, clock=infrastructure_clock)
            hold_transaction.wait(timeout=10)
            return created

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: schedule_concurrently(), range(2)))
    assert sorted(results) == [0, 1]
    with session_factory.begin() as session:
        assert schedule(session, clock=infrastructure_clock) == 0
        assert session.scalar(select(func.count(Reminder.id))) == 1
        assert session.scalar(select(func.count(ReminderDayGuard.id))) == 1


def test_old_title_consolidates_skipped_stages_and_stops_after_d7(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    create_title(session_factory, due=date(2026, 8, 1))
    assert run_once(session_factory, clock=infrastructure_clock)
    for offset in (1, 8, 60):
        set_business_time(
            session_factory, datetime(2026, 8, 17, 10, tzinfo=BUSINESS_TZ) + timedelta(days=offset)
        )
        assert not run_once(session_factory, clock=infrastructure_clock)
    with session_factory() as session:
        job = session.scalar(select(Reminder))
        assert job is not None and job.stage == 7 and job.status == "sent"
        skipped = session.scalars(
            select(AuditEvent).where(AuditEvent.type == "reminder.stage_skipped")
        ).all()
        assert sorted(event.details["stage"] for event in skipped) == [-3, 0, 3]
        assert session.scalar(select(func.count(Reminder.id))) == 1
        assert session.scalar(select(func.count(Delivery.id))) == 1


def test_latest_stage_supersedes_pending_and_daily_limit_is_preserved(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    create_title(session_factory)
    set_business_time(session_factory, datetime(2026, 8, 20, 8, tzinfo=BUSINESS_TZ))
    with session_factory.begin() as session:
        assert schedule(session, clock=infrastructure_clock) == 1
    set_business_time(session_factory, datetime(2026, 8, 20, 9, tzinfo=BUSINESS_TZ))
    with session_factory.begin() as session:
        assert schedule(session, clock=infrastructure_clock) == 0
    assert job_state(session_factory) == ("superseded", 0)
    set_business_time(session_factory, datetime(2026, 8, 21, 10, tzinfo=BUSINESS_TZ))
    with session_factory.begin() as session:
        assert schedule(session, clock=infrastructure_clock) == 1
        jobs = session.scalars(select(Reminder).order_by(Reminder.id)).all()
        assert [(job.stage, job.status) for job in jobs] == [(-3, "superseded"), (0, "pending")]


def test_known_no_effect_retry_is_superseded_by_later_stage(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    create_title(session_factory, scenario="transient")
    assert run_once(session_factory, clock=infrastructure_clock)
    assert job_state(session_factory) == ("retry_scheduled", 1)
    set_business_time(session_factory, datetime(2026, 8, 20, 10, tzinfo=BUSINESS_TZ))
    with session_factory.begin() as session:
        assert schedule(session, clock=infrastructure_clock) == 1
        jobs = session.scalars(select(Reminder).order_by(Reminder.id)).all()
        assert [(job.stage, job.status) for job in jobs] == [(-3, "superseded"), (0, "pending")]


def test_two_workers_claim_one_job_without_waiting_on_each_other(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    create_title(session_factory)
    with session_factory.begin() as session:
        schedule(session, clock=infrastructure_clock)
    start = Barrier(2)
    hold_transaction = Barrier(2)

    def claim_concurrently() -> Claim | None:
        with session_factory.begin() as session:
            start.wait(timeout=10)
            possession = claim(session, clock=infrastructure_clock)
            hold_transaction.wait(timeout=10)
            return possession

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim_concurrently(), range(2)))
    assert sum(result is not None for result in results) == 1


def test_transient_retry_is_durable_and_uses_infrastructure_time(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    create_title(session_factory, scenario="transient")
    assert run_once(session_factory, clock=infrastructure_clock)
    assert job_state(session_factory) == ("retry_scheduled", 1)
    set_business_time(session_factory, datetime(2026, 8, 18, 10, tzinfo=BUSINESS_TZ))
    assert not run_once(session_factory, clock=infrastructure_clock)
    infrastructure_clock.instant += timedelta(seconds=1)
    assert run_once(session_factory, clock=infrastructure_clock)
    assert job_state(session_factory) == ("sent", 2)
    with session_factory() as session:
        attempts = session.scalars(select(Attempt).order_by(Attempt.number)).all()
        assert [attempt.outcome for attempt in attempts] == ["transient", "success"]
        assert len({attempt.payload["idempotency_key"] for attempt in attempts}) == 1
        assert session.scalar(select(func.count(Delivery.id))) == 1


def test_permanent_failure_is_not_retried(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    create_title(session_factory, scenario="permanent")
    assert run_once(session_factory, clock=infrastructure_clock)
    infrastructure_clock.instant += timedelta(hours=1)
    assert not run_once(session_factory, clock=infrastructure_clock)
    assert job_state(session_factory) == ("failed", 1)
    with session_factory() as session:
        assert session.scalar(select(func.count(Delivery.id))) == 0


def test_retry_exhaustion_has_five_attempts_and_growing_delays(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    create_title(session_factory, scenario="always_transient")
    assert run_once(session_factory, clock=infrastructure_clock)
    for expected_count, delay in enumerate((1, 2, 4, 8), start=1):
        assert job_state(session_factory) == ("retry_scheduled", expected_count)
        with session_factory() as session:
            job = session.scalar(select(Reminder))
            assert job is not None
            assert job.next_attempt_at - infrastructure_clock.now() == timedelta(seconds=delay)
        infrastructure_clock.instant += timedelta(seconds=delay)
        assert run_once(session_factory, clock=infrastructure_clock)
    assert job_state(session_factory) == ("failed", 5)
    infrastructure_clock.instant += timedelta(hours=1)
    assert not run_once(session_factory, clock=infrastructure_clock)


def test_lost_response_replays_same_attempt_after_provider_restart(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    create_title(session_factory, scenario="response_lost")
    assert run_once(session_factory, clock=infrastructure_clock)
    assert job_state(session_factory) == ("retry_scheduled", 1)
    with session_factory() as session:
        attempt = session.scalar(select(Attempt))
        assert attempt is not None and attempt.outcome == "unknown"
        assert session.scalar(select(func.count(Delivery.id))) == 1
        assert session.scalar(select(func.count(ProviderResult.attempt_id))) == 1
    infrastructure_clock.instant += timedelta(seconds=1)
    new_provider = FakeProvider(session_factory, infrastructure_clock)
    assert run_once(session_factory, clock=infrastructure_clock, provider=new_provider)
    assert job_state(session_factory) == ("sent", 1)
    with session_factory() as session:
        assert session.scalar(select(func.count(Attempt.id))) == 1
        assert session.scalar(select(func.count(Delivery.id))) == 1


def test_unknown_reconciliation_reserves_day_and_blocks_later_stage(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    create_title(session_factory, scenario="response_lost")
    assert run_once(session_factory, clock=infrastructure_clock)
    set_business_time(session_factory, datetime(2026, 8, 20, 10, tzinfo=BUSINESS_TZ))
    with session_factory.begin() as session:
        assert schedule(session, clock=infrastructure_clock) == 0
        assert session.scalar(select(func.count(Reminder.id))) == 1
    infrastructure_clock.instant += timedelta(seconds=1)
    assert run_once(session_factory, clock=infrastructure_clock)
    with session_factory.begin() as session:
        assert schedule(session, clock=infrastructure_clock) == 0
        assert session.scalar(select(func.count(Reminder.id))) == 1
    set_business_time(session_factory, datetime(2026, 8, 21, 10, tzinfo=BUSINESS_TZ))
    with session_factory.begin() as session:
        assert schedule(session, clock=infrastructure_clock) == 1


def test_missing_provider_result_is_replayed_not_assumed_to_have_no_effect(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    class InterruptedProvider:
        def send(self, attempt_id: int) -> SendResult:
            raise ConnectionError("simulação de interrupção antes de uma resposta")

    create_title(session_factory)
    assert run_once(session_factory, clock=infrastructure_clock, provider=InterruptedProvider())
    assert job_state(session_factory) == ("retry_scheduled", 1)
    with session_factory() as session:
        assert session.scalar(select(func.count(ProviderResult.attempt_id))) == 0
    infrastructure_clock.instant += timedelta(seconds=1)
    assert run_once(session_factory, clock=infrastructure_clock)
    assert job_state(session_factory) == ("sent", 1)


def test_recovery_after_acceptance_fences_late_worker_result(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    create_title(session_factory)
    with session_factory.begin() as session:
        schedule(session, clock=infrastructure_clock)
    old_claim, attempt_id = take_job(session_factory, infrastructure_clock)
    provider = FakeProvider(session_factory, infrastructure_clock)
    assert provider.send(attempt_id).outcome == "success"
    # O processo morreu depois da aceitação e antes de gravar finish.
    infrastructure_clock.instant += timedelta(seconds=61)
    new_claim, recovered_attempt_id = take_job(session_factory, infrastructure_clock)
    assert recovered_attempt_id == attempt_id
    assert new_claim.token == old_claim.token + 1
    with session_factory.begin() as session:
        assert not renew(session, old_claim, clock=infrastructure_clock)
        assert not finish(
            session,
            old_claim,
            attempt_id,
            SendResult("permanent", "resposta antiga"),
            clock=infrastructure_clock,
        )
    replay = FakeProvider(session_factory, infrastructure_clock).send(attempt_id)
    with session_factory.begin() as session:
        assert finish(session, new_claim, attempt_id, replay, clock=infrastructure_clock)
    assert job_state(session_factory) == ("sent", 1)
    with session_factory() as session:
        assert session.scalar(select(func.count(Delivery.id))) == 1


def test_lease_renewal_cannot_resurrect_expired_possession(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    create_title(session_factory)
    with session_factory.begin() as session:
        schedule(session, clock=infrastructure_clock)
    possession, _ = take_job(session_factory, infrastructure_clock)
    infrastructure_clock.instant += timedelta(seconds=20)
    with session_factory.begin() as session:
        assert renew(session, possession, clock=infrastructure_clock)
        job = session.get(Reminder, possession.reminder_id)
        assert job is not None
        assert job.lease_expires_at == infrastructure_clock.now() + timedelta(seconds=60)
    infrastructure_clock.instant += timedelta(seconds=61)
    with session_factory.begin() as session:
        assert not renew(session, possession, clock=infrastructure_clock)


def test_restart_before_authorization_consolidates_into_latest_stage(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    create_title(session_factory)
    with session_factory.begin() as session:
        schedule(session, clock=infrastructure_clock)
    with session_factory.begin() as session:
        old_claim = claim(session, clock=infrastructure_clock)
        assert old_claim is not None
    set_business_time(session_factory, datetime(2026, 8, 20, 10, tzinfo=BUSINESS_TZ))
    infrastructure_clock.instant += timedelta(seconds=61)
    assert run_once(session_factory, clock=infrastructure_clock)
    with session_factory() as session:
        jobs = session.scalars(select(Reminder).order_by(Reminder.id)).all()
        assert [(job.stage, job.status, job.attempts_count) for job in jobs] == [
            (-3, "superseded", 0),
            (0, "sent", 1),
        ]


def test_concurrent_provider_replays_have_one_delivery(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    create_title(session_factory)
    with session_factory.begin() as session:
        schedule(session, clock=infrastructure_clock)
    _, attempt_id = take_job(session_factory, infrastructure_clock)
    start = Barrier(2)

    def send_concurrently() -> SendResult:
        start.wait(timeout=10)
        return FakeProvider(session_factory, infrastructure_clock).send(attempt_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: send_concurrently(), range(2)))
    assert all(result.outcome == "success" for result in results)
    with session_factory() as session:
        assert session.scalar(select(func.count(Delivery.id))) == 1
        assert session.scalar(select(func.count(ProviderResult.attempt_id))) == 1


def test_provider_result_is_immutable_for_transient_attempt(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    create_title(session_factory, scenario="transient")
    with session_factory.begin() as session:
        schedule(session, clock=infrastructure_clock)
    _, attempt_id = take_job(session_factory, infrastructure_clock)
    assert (
        FakeProvider(session_factory, infrastructure_clock).send(attempt_id).outcome == "transient"
    )
    assert (
        FakeProvider(session_factory, infrastructure_clock).send(attempt_id).outcome == "transient"
    )
    with session_factory() as session:
        assert session.scalar(select(func.count(Delivery.id))) == 0


def test_closing_title_before_authorization_cancels_claimed_job(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    title_id = create_title(session_factory)
    with session_factory.begin() as session:
        schedule(session, clock=infrastructure_clock)
    with session_factory.begin() as session:
        possession = claim(session, clock=infrastructure_clock)
        assert possession is not None
    with session_factory.begin() as session:
        pay(session, title_id, "payment-before-authorization", "", 1)
    with session_factory.begin() as session:
        assert authorize(session, possession, clock=infrastructure_clock) is None
        assert session.scalar(select(func.count(Attempt.id))) == 0
    assert job_state(session_factory) == ("canceled", 0)


def test_previous_authorization_remains_reconcilable_after_payment(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    title_id = create_title(session_factory, scenario="response_lost")
    with session_factory.begin() as session:
        schedule(session, clock=infrastructure_clock)
    possession, attempt_id = take_job(session_factory, infrastructure_clock)
    with session_factory.begin() as session:
        pay(session, title_id, "payment-after-authorization", "", 1)
    with pytest.raises(ResponseLost):
        FakeProvider(session_factory, infrastructure_clock).send(attempt_id)
    with session_factory.begin() as session:
        assert finish(
            session,
            possession,
            attempt_id,
            SendResult("unknown", "resposta perdida"),
            clock=infrastructure_clock,
        )
    infrastructure_clock.instant += timedelta(seconds=1)
    assert run_once(session_factory, clock=infrastructure_clock)
    assert job_state(session_factory) == ("sent", 1)
    with session_factory() as session:
        assert session.scalar(select(func.count(Delivery.id))) == 1
        job = session.scalar(select(Reminder))
        assert job is not None and job.cancel_requested


def test_reconciliation_without_effect_after_payment_cannot_authorize_retry(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    title_id = create_title(session_factory, scenario="transient")
    with session_factory.begin() as session:
        schedule(session, clock=infrastructure_clock)
    possession, attempt_id = take_job(session_factory, infrastructure_clock)
    with session_factory.begin() as session:
        pay(session, title_id, "payment-before-no-effect-reconciliation", "", 1)
    result = FakeProvider(session_factory, infrastructure_clock).send(attempt_id)
    with session_factory.begin() as session:
        assert finish(session, possession, attempt_id, result, clock=infrastructure_clock)
    assert job_state(session_factory) == ("canceled", 1)
    infrastructure_clock.instant += timedelta(hours=1)
    assert not run_once(session_factory, clock=infrastructure_clock)


@pytest.mark.parametrize("first_action", ["payment", "authorization"])
def test_payment_authorization_race_has_explicit_lock_order(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock, first_action: str
) -> None:
    title_id = create_title(session_factory)
    with session_factory.begin() as session:
        schedule(session, clock=infrastructure_clock)
    with session_factory.begin() as session:
        possession = claim(session, clock=infrastructure_clock)
        assert possession is not None
    rendezvous = Barrier(2)

    def perform(session: Session, action: str) -> int | None:
        if action == "payment":
            pay(session, title_id, "payment-concurrent-with-authorization", "", 1)
            return None
        attempt = authorize(session, possession, clock=infrastructure_clock)
        return attempt.id if attempt is not None else None

    def winner() -> int | None:
        with session_factory.begin() as session:
            result = perform(session, first_action)
            # A operação terminou, mas seu lock do título ainda está retido.
            # A outra conexão já existe quando liberamos o commit vencedor.
            rendezvous.wait(timeout=10)
            return result

    def follower() -> int | None:
        with session_factory.begin() as session:
            session.connection()
            rendezvous.wait(timeout=10)
            return perform(session, "authorization" if first_action == "payment" else "payment")

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(winner)
        second = pool.submit(follower)
        attempts = [first.result(timeout=15), second.result(timeout=15)]
    if first_action == "payment":
        assert attempts == [None, None]
        assert job_state(session_factory) == ("canceled", 0)
    else:
        attempt_id = attempts[0]
        assert attempt_id is not None
        result = FakeProvider(session_factory, infrastructure_clock).send(attempt_id)
        with session_factory.begin() as session:
            assert finish(session, possession, attempt_id, result, clock=infrastructure_clock)
        assert job_state(session_factory) == ("sent", 1)


def test_paused_worker_plans_but_does_not_authorize_until_enabled(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    create_title(session_factory)
    with session_factory.begin() as session:
        demo = session.get(DemoState, 1)
        assert demo is not None
        demo.worker_enabled = False
    assert not run_once(session_factory, clock=infrastructure_clock)
    with session_factory() as session:
        assert session.scalar(select(func.count(Reminder.id))) == 1
        assert session.scalar(select(func.count(Attempt.id))) == 0
    assert job_state(session_factory) == ("pending", 0)


def test_draining_existing_queue_does_not_rescan_newly_imported_titles(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    first_title_id = create_title(session_factory)
    with session_factory.begin() as session:
        assert schedule(session, clock=infrastructure_clock) == 1
        first_title = session.get(Receivable, first_title_id)
        assert first_title is not None
        second_title = Receivable(
            source_system="reminder-tests",
            external_receivable_id="T2",
            customer_id=first_title.customer_id,
            description="Título importado depois do agendamento",
            amount_cents=100,
            due_date=first_title.due_date,
            status="open",
            scenario="success",
        )
        session.add(second_title)
        session.flush()
        second_title_id = second_title.id
    assert run_once(session_factory, clock=infrastructure_clock, schedule_pending=False)
    with session_factory() as session:
        assert session.scalar(select(func.count(Delivery.id))) == 1
        assert (
            session.scalar(select(Reminder.id).where(Reminder.receivable_id == second_title_id))
            is None
        )
    assert not run_once(session_factory, clock=infrastructure_clock, schedule_pending=False)
    assert run_once(session_factory, clock=infrastructure_clock)
    with session_factory() as session:
        assert session.scalar(select(func.count(Delivery.id))) == 2


def test_draining_without_scheduling_revalidates_current_stage_before_authorizing(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    create_title(session_factory)
    with session_factory.begin() as session:
        assert schedule(session, clock=infrastructure_clock) == 1
    set_business_time(session_factory, datetime(2026, 8, 20, 10, tzinfo=BUSINESS_TZ))
    assert run_once(session_factory, clock=infrastructure_clock, schedule_pending=False)
    assert job_state(session_factory) == ("superseded", 0)
    with session_factory() as session:
        assert session.scalar(select(func.count(Delivery.id))) == 0
    assert run_once(session_factory, clock=infrastructure_clock)
    with session_factory() as session:
        job = session.scalar(select(Reminder).where(Reminder.stage == 0))
        assert job is not None and job.status == "sent"


@pytest.mark.parametrize("scenario", ["always_transient", "response_lost"])
def test_demo_retry_base_scales_transient_and_uncertain_next_attempt(
    session_factory: sessionmaker[Session],
    infrastructure_clock: FixedClock,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    monkeypatch.setattr(get_settings(), "demo_retry_base_seconds", 2.0)
    create_title(session_factory, scenario=scenario)
    assert run_once(session_factory, clock=infrastructure_clock)
    with session_factory() as session:
        job = session.scalar(select(Reminder))
        assert job is not None and job.status == "retry_scheduled"
        assert job.next_attempt_at == infrastructure_clock.now() + timedelta(seconds=2)
    infrastructure_clock.instant += timedelta(seconds=1)
    assert not run_once(session_factory, clock=infrastructure_clock)
    infrastructure_clock.instant += timedelta(seconds=1)
    assert run_once(session_factory, clock=infrastructure_clock)
    with session_factory() as session:
        job = session.scalar(select(Reminder))
        assert job is not None
        if scenario == "always_transient":
            assert job.attempts_count == 2
            assert job.next_attempt_at == infrastructure_clock.now() + timedelta(seconds=4)
        else:
            assert job.status == "sent" and job.attempts_count == 1


def test_idle_scheduler_uses_bounded_queries_without_rewriting_audit(
    session_factory: sessionmaker[Session], infrastructure_clock: FixedClock
) -> None:
    from sqlalchemy import event

    from gestao_recebiveis.database import engine
    from gestao_recebiveis.seed import seed_demo

    with session_factory.begin() as session:
        seed_demo(session)
        assert schedule(session, clock=infrastructure_clock) > 100
    statements: list[str] = []

    def capture(*args: object) -> None:
        statements.append(str(args[2]).split()[0].upper())

    event.listen(engine, "before_cursor_execute", capture)
    try:
        with session_factory.begin() as session:
            assert schedule(session, clock=infrastructure_clock) == 0
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert statements.count("SELECT") <= 4
    assert not {"INSERT", "UPDATE", "DELETE"}.intersection(statements)
