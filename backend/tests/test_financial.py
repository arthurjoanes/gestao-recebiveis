from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from gestao_recebiveis.errors import DomainError
from gestao_recebiveis.import_csv import cents
from gestao_recebiveis.imports import confirm_batch, create_preview
from gestao_recebiveis.models import AuditEvent, Customer, DemoState, Payment, Receivable
from gestao_recebiveis.receivables import cancel, pay
from gestao_recebiveis.reporting import overview
from gestao_recebiveis.seed import seed_demo

HEADER = "source_system,external_receivable_id,external_customer_id,customer_name,customer_email,description,amount_brl,due_date\n"
LINES = [
    "manual,A,C1,Cliente Ficticio Um,um@example.com,Centavo,0.01,2026-08-16\n",
    "manual,B,C1,Cliente Ficticio Um,um@example.com,Dez centavos,0.10,2026-08-17\n",
    "manual,C,C2,Cliente Ficticio Dois,dois@example.com,Dez reais,10.20,2026-08-18\n",
]


def load(session: Session, content: str = HEADER + "".join(LINES)) -> int:
    batch = create_preview(session, "manual.csv", content.encode(), 1)
    confirm_batch(session, batch.id, 1)
    return batch.id


def test_repeat_reorder_and_renamed_no_duplicate(db: Session) -> None:
    for lines in (LINES, list(reversed(LINES)), LINES + [LINES[0]]):
        batch_id = load(db, HEADER + "".join(lines))
        assert confirm_batch(db, batch_id, 1).status == "confirmed"
    assert db.scalar(select(func.count(Receivable.id))) == 3
    assert db.scalar(select(func.count(Customer.id))) == 2
    assert db.scalar(select(func.sum(Receivable.amount_cents))) == 1031


def test_error_last_line_and_conflict_atomic(db: Session) -> None:
    bad = load(db, HEADER + LINES[0] + LINES[1].replace("0.10", "0.001"))
    assert confirm_batch(db, bad, 1).status == "rejected"
    assert db.scalar(select(func.count(Receivable.id))) == 0
    assert db.scalar(select(func.count(Customer.id))) == 0
    load(db, HEADER + LINES[0])
    conflict = load(db, HEADER + LINES[1] + LINES[0].replace("0.01", "0.02"))
    assert confirm_batch(db, conflict, 1).status == "rejected"
    assert db.scalar(select(func.count(Receivable.id))) == 1
    assert (
        db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.type == "receivable_imported"))
        == 1
    )


def test_contradictory_internal_lines_and_customer_conflict(db: Session) -> None:
    batch_id = load(db, HEADER + LINES[0] + LINES[0].replace("0.01", "1.00"))
    batch = confirm_batch(db, batch_id, 1)
    assert {e["line"] for e in batch.report["errors"]} == {2, 3}
    assert db.scalar(select(func.count(Receivable.id))) == 0
    load(db)
    batch_id = load(db, HEADER + LINES[0].replace("Cliente Ficticio Um", "Nome Alterado"))
    assert confirm_batch(db, batch_id, 1).status == "rejected"


def test_preview_revalidated(db: Session, session_factory: sessionmaker[Session]) -> None:
    preview = create_preview(db, "old.csv", (HEADER + LINES[0]).encode(), 1)
    db.commit()
    with session_factory.begin() as other:
        load(other, HEADER + LINES[0].replace("0.01", "4.00"))
    result = confirm_batch(db, preview.id, 1)
    assert result.status == "rejected"
    assert db.scalar(select(Receivable.amount_cents)) == 400


@pytest.mark.parametrize(
    "value", ["0.001", "1e2", "1,00", "-1.00", "+1", "NaN", "0", "92233720368547758.08"]
)
def test_ambiguous_money_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        cents(value)


@pytest.mark.parametrize("value,expected", [("0.01", 1), ("0.10", 10), ("10.20", 1020), ("1", 100)])
def test_exact_cents(value: str, expected: int) -> None:
    assert cents(value) == expected


def test_payment_idempotency_cancel_and_totals(db: Session) -> None:
    load(db)
    payment = pay(db, 1, "payment-key-1", "Conferido", 1)
    assert pay(db, 1, "payment-key-1", "Conferido", 1).id == payment.id
    with pytest.raises(DomainError, match="outro conteúdo"):
        pay(db, 1, "payment-key-1", "Alterado", 1)
    with pytest.raises(DomainError):
        pay(db, 1, "different-key", "", 1)
    with pytest.raises(DomainError):
        cancel(db, 1, "Não permitido", 1)
    cancel(db, 2, "Cancelamento de teste", 1)
    cancel(db, 2, "Cancelamento repetido", 1)
    with pytest.raises(DomainError):
        pay(db, 2, "canceled-title", "", 1)
    result = overview(db, "", None, None, None, None)
    assert result["open_cents"] == "1020"
    assert result["received_cents"] == "1"
    assert result["canceled_count"] == 1
    assert db.scalar(select(func.count(Payment.id))) == 1
    load(db)  # reimportação não reabre títulos pagos/cancelados
    assert db.get(Receivable, 1).status == "paid"


def test_midnight_and_received_period_independent_of_due_filter(db: Session) -> None:
    load(db)
    state = db.get(DemoState, 1)
    assert state
    state.business_now = datetime.fromisoformat("2026-08-17T02:59:59+00:00")
    assert overview(db, "", None, None, None, None)["overdue_cents"] == "0"
    state.business_now = datetime.fromisoformat("2026-08-17T03:00:00+00:00")
    assert overview(db, "", None, None, None, None)["overdue_cents"] == "1"
    pay(db, 1, "midnight-pay", "", 1)
    result = overview(db, "", datetime(2026, 8, 18).date(), None, None, None)
    assert result["received_cents"] == "1"
    assert result["open_cents"] == "1020"


def test_concurrent_imports_identical_and_conflicting(
    session_factory: sessionmaker[Session],
) -> None:
    def race(contents: list[str]) -> list[str]:
        barrier = Barrier(2)

        def task(content: str) -> str:
            with session_factory.begin() as session:
                batch = create_preview(session, "race.csv", content.encode(), 1)
                batch_id = batch.id
            barrier.wait(timeout=10)
            with session_factory.begin() as session:
                return confirm_batch(session, batch_id, 1).status

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(task, contents))

    assert race([HEADER + LINES[0]] * 2) == ["confirmed", "confirmed"]
    other = LINES[1].replace(",B,", ",D,")
    assert sorted(race([HEADER + other, HEADER + other.replace("0.10", "0.20")])) == [
        "confirmed",
        "rejected",
    ]
    with session_factory() as session:
        assert session.scalar(select(func.count(Receivable.id))) == 2


def test_concurrent_same_payment_and_cancel_race(session_factory: sessionmaker[Session]) -> None:
    with session_factory.begin() as session:
        load(session)
    barrier = Barrier(2)

    def payment_task(_: int) -> int:
        barrier.wait(timeout=10)
        with session_factory.begin() as session:
            return pay(session, 1, "same-payment-key", "", 1).id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(payment_task, [1, 2]))
    assert ids[0] == ids[1]
    barrier = Barrier(2)

    def transition(action: str) -> str:
        barrier.wait(timeout=10)
        try:
            with session_factory.begin() as session:
                if action == "pay":
                    pay(session, 2, "racing-payment", "", 1)
                else:
                    cancel(session, 2, "Concorrência", 1)
            return "ok"
        except DomainError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(transition, ["pay", "cancel"])) == ["conflict", "ok"]

    with session_factory() as session:
        first_payments = session.scalars(select(Payment).where(Payment.receivable_id == 1)).all()
        assert len(first_payments) == 1
        assert first_payments[0].amount_cents == 1
        assert session.get(Receivable, 1).status == "paid"
        first_events = session.scalars(
            select(AuditEvent).where(
                AuditEvent.receivable_id == 1, AuditEvent.type == "payment_recorded"
            )
        ).all()
        assert len(first_events) == 1
        second = session.get(Receivable, 2)
        second_payments = session.scalars(select(Payment).where(Payment.receivable_id == 2)).all()
        financial_events = session.scalars(
            select(AuditEvent).where(
                AuditEvent.receivable_id == 2,
                AuditEvent.type.in_(("payment_recorded", "receivable_canceled")),
            )
        ).all()
        assert len(financial_events) == 1
        if second.status == "paid":
            assert len(second_payments) == 1 and second_payments[0].amount_cents == 10
            assert financial_events[0].type == "payment_recorded"
        else:
            assert second.status == "canceled" and not second_payments
            assert financial_events[0].type == "receivable_canceled"


def test_concurrent_payment_key_cannot_pay_two_titles(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory.begin() as session:
        load(session)
    barrier = Barrier(2)

    def attempt_payment(title_id: int) -> tuple[int, str]:
        barrier.wait(timeout=10)
        try:
            with session_factory.begin() as session:
                pay(session, title_id, "shared-key-two-titles", "", 1)
            return title_id, "paid"
        except DomainError as error:
            assert error.code == "idempotency_conflict"
            return title_id, "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = dict(pool.map(attempt_payment, [1, 2]))
    assert sorted(outcomes.values()) == ["conflict", "paid"]
    winner = next(title_id for title_id, outcome in outcomes.items() if outcome == "paid")
    with session_factory() as session:
        payment = session.scalars(select(Payment)).one()
        assert payment.receivable_id == winner
        assert payment.amount_cents == {1: 1, 2: 10}[winner]
        assert session.get(Receivable, winner).status == "paid"
        assert session.get(Receivable, 3 - winner).status == "open"
        assert (
            session.scalar(
                select(func.count(AuditEvent.id)).where(AuditEvent.type == "payment_recorded")
            )
            == 1
        )


def test_seed_repeat_does_not_multiply(db: Session) -> None:
    seed_demo(db)
    seed_demo(db)
    assert db.scalar(select(func.count(Customer.id))) == 60
    assert db.scalar(select(func.count(Receivable.id))) == 240
    assert db.scalar(select(func.count(Payment.id))) == 48


def test_stale_title_reloaded_before_financial_transition(
    db: Session, session_factory: sessionmaker[Session]
) -> None:
    load(db)
    db.commit()
    cached = db.get(Receivable, 1)
    assert cached and cached.status == "open"
    with session_factory.begin() as other:
        pay(other, 1, "stale-session-payment", "", 1)
    with pytest.raises(DomainError):
        cancel(db, 1, "Não pode cancelar uma baixa concorrente", 1)
    assert cached.status == "paid"


def test_stale_preview_reconfirmation_preserves_result(
    db: Session, session_factory: sessionmaker[Session]
) -> None:
    preview = create_preview(db, "cached.csv", (HEADER + LINES[0]).encode(), 1)
    db.commit()
    assert preview.status == "preview"
    with session_factory.begin() as other:
        confirmed = confirm_batch(other, preview.id, 1)
        original = confirmed.report
    repeated = confirm_batch(db, preview.id, 1)
    assert repeated.report == original
    assert repeated.report["new_count"] == 1
    assert (
        db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.type == "import_confirmed"))
        == 1
    )


def test_extreme_received_dates_do_not_overflow(db: Session) -> None:
    from datetime import date

    load(db)
    pay(db, 1, "extreme-period-pay", "", 1)
    assert overview(db, "", None, None, date.min, date.max)["received_cents"] == "1"


def test_manual_fixture_independent_total(db: Session) -> None:
    from pathlib import Path

    fixture = Path("/data/fixtures/manual.csv").read_text(encoding="utf-8")
    load(db, fixture)
    assert db.scalar(select(func.sum(Receivable.amount_cents))) == 123486
    assert db.scalar(select(func.count(Receivable.id))) == 3


@pytest.mark.parametrize("replacement", ["nao-e-email", "2026-02-30"])
def test_import_validation_explains_invalid_field_in_portuguese(
    db: Session, replacement: str
) -> None:
    original = "um@example.com" if replacement == "nao-e-email" else "2026-08-16"
    batch_id = load(db, HEADER + LINES[0].replace(original, replacement))
    result = confirm_batch(db, batch_id, 1)
    assert result.status == "rejected"
    assert "inválid" in result.report["errors"][0]["message"]
