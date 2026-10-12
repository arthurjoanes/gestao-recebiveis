from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from threading import Barrier
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.orm import Session, sessionmaker
from test_api import login

from gestao_recebiveis import reporting
from gestao_recebiveis.database import engine, read_snapshot
from gestao_recebiveis.models import Customer, DemoState, Receivable
from gestao_recebiveis.receivables import cancel, pay

TODAY = date(2026, 8, 17)
MAX_CENTS = 9223372036854775807


def customer(db: Session, external_id: str = "REPORTS") -> Customer:
    item = Customer(
        source_system="synthetic",
        external_customer_id=external_id,
        name="Cliente Fictício do Relatório",
        email="reports@example.com",
    )
    db.add(item)
    db.flush()
    return item


def receivable(db: Session, owner: Customer, code: str, days: int, cents: int = 100) -> Receivable:
    item = Receivable(
        source_system=owner.source_system,
        external_receivable_id=code,
        customer_id=owner.id,
        description="Relatório sintético",
        amount_cents=cents,
        due_date=TODAY - timedelta(days=days),
        status="open",
        scenario="success",
    )
    db.add(item)
    db.flush()
    return item


def test_aging_inclusive_boundaries_residual_and_drilldown(client: TestClient, db: Session) -> None:
    owner = customer(db)
    for days in (-1, 0, 1, 30, 31, 60, 61, 90, 91):
        title = receivable(db, owner, f"BOUNDARY-{days}", days)
        if days == 30:
            pay(db, title.id, "aging-partial-30", "", 1, "25")
            pay(db, title.id, "aging-partial-30-second", "", 1, "1")
    closed = receivable(db, owner, "PAID", 1)
    pay(db, closed.id, "aging-paid-excluded", "", 1)
    canceled = receivable(db, owner, "CANCELED", 31)
    cancel(db, canceled.id, "Cancelamento sintético", 1)
    other = customer(db, "OTHER")
    receivable(db, other, "OTHER-CUSTOMER", 1)
    db.commit()
    login(client, "leitor")
    filters = {
        "customer_id": owner.id,
        "q": "BOUNDARY",
        "due_from": "2026-01-01",
        "due_to": "2026-12-31",
    }
    response = client.get("/api/v1/reports/aging", params={**filters, "page_size": 2})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["business_date"] == "2026-08-17"
    assert result["total"] == result["title_count"] == 9
    assert len(result["items"]) == 2
    assert result["open_cents"] == "874"
    assert [
        (row["key"], row["title_count"], row["remaining_cents"]) for row in result["buckets"]
    ] == [
        ("current", 2, "200"),
        ("1_30", 2, "174"),
        ("31_60", 2, "200"),
        ("61_90", 2, "200"),
        ("over_90", 1, "100"),
    ]
    assert sum(int(row["remaining_cents"]) for row in result["buckets"]) == int(
        result["open_cents"]
    )
    for bucket in result["buckets"]:
        report = client.get(
            "/api/v1/reports/aging", params={**filters, "bucket": bucket["key"]}
        ).json()
        drilldown = client.get(
            "/api/v1/receivables", params={**filters, "aging_bucket": bucket["key"]}
        ).json()
        assert report["open_cents"] == bucket["remaining_cents"]
        assert report["total"] == drilldown["total"] == bucket["title_count"]
        assert [row["id"] for row in report["items"]] == [row["id"] for row in drilldown["items"]]
        assert all(row["aging_bucket"] == bucket["key"] for row in report["items"])
    again = client.get("/api/v1/reports/aging", params={**filters, "page_size": 2}).json()
    assert [row["id"] for row in result["items"]] == [row["id"] for row in again["items"]]


def test_reports_exact_sums_above_bigint_and_javascript_limit(
    client: TestClient, db: Session
) -> None:
    owner = customer(db)
    for index in range(2):
        title = receivable(db, owner, f"BIG-{index}", 1, MAX_CENTS)
        pay(db, title.id, f"report-big-{index}", "", 1, "1")
    db.commit()
    login(client)
    expected = str(2 * (MAX_CENTS - 1))
    assert client.get("/api/v1/reports/aging").json()["open_cents"] == expected
    assert client.get("/api/v1/overview").json()["open_cents"] == expected
    result = client.get(f"/api/v1/customers/{owner.id}/statement", params={"page_size": 1}).json()
    assert result["totals"]["amount_cents"] == str(2 * MAX_CENTS)
    assert result["totals"]["remaining_cents"] == expected
    assert result["totals"]["paid_cents"] == "2"
    assert result["titles"]["total"] == 2 and len(result["titles"]["items"]) == 1


def test_statement_identity_empty_customer_and_missing(client: TestClient, db: Session) -> None:
    empty = customer(db, "EMPTY")
    same_name = customer(db, "SAME-NAME")
    title = receivable(db, same_name, "SAME-NAME-TITLE", 0)
    pay(db, title.id, "statement-another-customer", "", 1)
    db.commit()
    login(client, "leitor")
    response = client.get(f"/api/v1/customers/{empty.id}/statement")
    assert response.status_code == 200
    result = response.json()
    assert result["customer"]["external_customer_id"] == "EMPTY"
    assert result["customer"]["source_system"] == "synthetic"
    assert result["titles"]["items"] == result["payments"]["items"] == []
    assert result["totals"]["title_count"] == result["totals"]["paid_count"] == 0
    assert all(value == "0" for key, value in result["totals"].items() if key.endswith("_cents"))
    assert client.get("/api/v1/customers/2147483647/statement").status_code == 404
    client.cookies.clear()
    assert client.get("/api/v1/reports/aging").status_code == 401
    assert client.get(f"/api/v1/customers/{empty.id}/statement").status_code == 401


def test_statement_payment_period_and_due_filters_are_independent(
    client: TestClient, db: Session
) -> None:
    owner = customer(db)
    past = receivable(db, owner, "PAST", 40)
    future = receivable(db, owner, "FUTURE", -1)
    canceled = receivable(db, owner, "CANCELED", -1)
    pay(db, past.id, "statement-old-period", "Anterior", 1, "20")
    pay(db, future.id, "statement-future-period", "Mesmo dia", 1, "10")
    state = db.get(DemoState, 1)
    assert state
    state.business_now = datetime.fromisoformat("2026-08-18T10:00:00-03:00")
    pay(db, past.id, "statement-next-period", "Atual", 1, "30")
    cancel(db, canceled.id, "Cancelado sem recebimentos", 1)
    db.commit()
    login(client)
    response = client.get(
        f"/api/v1/customers/{owner.id}/statement",
        params={
            "due_from": "2026-08-18",
            "received_from": "2026-08-18",
            "received_to": "2026-08-18",
            "payment_page_size": 1,
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["totals"] == {
        "amount_cents": "200",
        "paid_cents": "10",
        "remaining_cents": "190",
        "open_cents": "90",
        "canceled_remaining_cents": "100",
        "title_count": 2,
        "received_cents": "30",
        "paid_count": 1,
    }
    assert result["payments"]["items"][0]["receivable_id"] == past.id
    assert result["payments"]["items"][0]["note"] == "Atual"
    unfiltered = client.get(
        f"/api/v1/customers/{owner.id}/statement",
        params={"received_from": "2026-08-18", "received_to": "2026-08-18"},
    ).json()
    assert unfiltered["totals"]["paid_cents"] == "60"
    assert unfiltered["totals"]["received_cents"] == "30"
    assert unfiltered["totals"]["paid_count"] == 1
    assert unfiltered["titles"]["items"][0]["remaining_cents"] == "50"
    all_receipts = client.get(
        f"/api/v1/customers/{owner.id}/statement",
        params={"received_from": "2026-08-17", "received_to": "2026-08-18", "payment_page_size": 1},
    ).json()
    assert all_receipts["payments"]["total"] == 3
    assert all_receipts["totals"]["paid_count"] == 3
    assert all_receipts["totals"]["received_cents"] == "60"
    second_page = client.get(
        f"/api/v1/customers/{owner.id}/statement",
        params={
            "received_from": "2026-08-17",
            "received_to": "2026-08-18",
            "payment_page_size": 1,
            "payment_page": 2,
        },
    ).json()
    assert second_page["totals"] == all_receipts["totals"]
    assert second_page["payments"]["items"][0]["id"] > all_receipts["payments"]["items"][0]["id"]


@pytest.mark.parametrize(
    "instant,expected",
    [("2026-08-18T02:59:59+00:00", "2026-08-17"), ("2026-08-18T03:00:00+00:00", "2026-08-18")],
)
def test_report_business_midnight_and_payment_day(
    client: TestClient, db: Session, instant: str, expected: str
) -> None:
    owner = customer(db)
    title = receivable(db, owner, "MIDNIGHT", 0)
    state = db.get(DemoState, 1)
    assert state
    state.business_now = datetime.fromisoformat(instant)
    pay(db, title.id, "report-midnight-partial", "", 1, "1")
    db.commit()
    login(client)
    report = client.get("/api/v1/reports/aging").json()
    assert report["business_date"] == expected
    assert report["items"][0]["aging_bucket"] == ("current" if expected == "2026-08-17" else "1_30")
    statement = client.get(
        f"/api/v1/customers/{owner.id}/statement",
        params={"received_from": expected, "received_to": expected},
    ).json()
    assert statement["totals"]["received_cents"] == "1" and statement["totals"]["paid_count"] == 1


@pytest.mark.parametrize("resource", ["aging", "statement"])
def test_report_snapshot_survives_payment_between_totals_and_lines(
    client: TestClient,
    db: Session,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    resource: str,
) -> None:
    owner = customer(db)
    title = receivable(db, owner, "SNAPSHOT", 0)
    db.commit()
    login(client)
    rendezvous = Barrier(2)
    original = reporting.list_titles

    def writer() -> None:
        rendezvous.wait(timeout=5)
        with session_factory.begin() as other:
            pay(other, title.id, "snapshot-payment", "", 1, "25")
            state = other.get(DemoState, 1)
            assert state
            state.business_now = datetime.fromisoformat("2026-08-18T10:00:00-03:00")
        rendezvous.wait(timeout=5)

    def after_totals(*args: Any, **kwargs: Any) -> dict[str, Any]:
        rendezvous.wait(timeout=5)
        rendezvous.wait(timeout=5)
        return original(*args, **kwargs)

    path = (
        "/api/v1/reports/aging"
        if resource == "aging"
        else f"/api/v1/customers/{owner.id}/statement"
    )
    monkeypatch.setattr(reporting, "list_titles", after_totals)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(writer)
        response = client.get(path)
        future.result(timeout=10)
    assert response.status_code == 200, response.text
    result = response.json()
    lines = result if resource == "aging" else result["titles"]
    assert result["business_date"] == "2026-08-17"
    assert lines["items"][0]["remaining_cents"] == "100"
    assert lines["items"][0]["paid_cents"] == "0"
    assert lines["items"][0]["payments"] == []
    if resource == "aging":
        assert result["open_cents"] == "100"
    else:
        assert result["totals"]["open_cents"] == "100"
        assert result["totals"]["received_cents"] == "0"
        assert result["payments"]["items"] == []
    monkeypatch.setattr(reporting, "list_titles", original)
    updated = client.get(path).json()
    updated_lines = updated if resource == "aging" else updated["titles"]
    assert updated["business_date"] == "2026-08-18"
    assert updated_lines["items"][0]["remaining_cents"] == "75"
    assert updated_lines["items"][0]["payments"][0]["amount_cents"] == "25"


def test_read_snapshot_is_read_only_and_does_not_change_write_isolation(db: Session) -> None:
    with read_snapshot() as snapshot:
        assert snapshot.scalar(text("SHOW transaction_isolation")) == "repeatable read"
        assert snapshot.scalar(text("SHOW transaction_read_only")) == "on"
    assert db.scalar(text("SHOW transaction_isolation")) == "read committed"
    assert db.scalar(text("SHOW transaction_read_only")) == "off"


def test_overview_snapshot_survives_payment_between_portfolio_and_receipts(
    client: TestClient,
    db: Session,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = customer(db)
    title = receivable(db, owner, "OVERVIEW-SNAPSHOT", 0)
    db.commit()
    login(client)
    rendezvous = Barrier(2)
    original = reporting.payment_filters

    def writer() -> None:
        rendezvous.wait(timeout=5)
        with session_factory.begin() as other:
            pay(other, title.id, "overview-snapshot-payment", "", 1)
        rendezvous.wait(timeout=5)

    def after_portfolio(*args: Any, **kwargs: Any) -> Any:
        rendezvous.wait(timeout=5)
        rendezvous.wait(timeout=5)
        return original(*args, **kwargs)

    monkeypatch.setattr(reporting, "payment_filters", after_portfolio)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(writer)
        response = client.get("/api/v1/overview")
        future.result(timeout=10)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["open_cents"] == "100" and result["open_count"] == 1
    assert result["received_cents"] == "0" and result["paid_count"] == 0
    monkeypatch.setattr(reporting, "payment_filters", original)
    updated = client.get("/api/v1/overview").json()
    assert updated["open_cents"] == "0" and updated["received_cents"] == "100"


def test_aging_query_count_stays_constant_for_full_page(client: TestClient, db: Session) -> None:
    owner = customer(db)
    for index in range(30):
        title = receivable(db, owner, f"BATCH-{index}", index)
        pay(db, title.id, f"batch-first-{index}", "", 1, "1")
        pay(db, title.id, f"batch-second-{index}", "", 1, "2")
    db.commit()
    login(client)
    queries: list[str] = []

    def observed(
        connection: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)

    event.listen(engine, "before_cursor_execute", observed)
    try:
        response = client.get("/api/v1/reports/aging", params={"page_size": 100})
    finally:
        event.remove(engine, "before_cursor_execute", observed)
    assert response.status_code == 200, response.text
    assert len(response.json()["items"]) == 30
    assert response.json()["open_cents"] == "2910"
    for item in response.json()["items"]:
        assert [payment["amount_cents"] for payment in item["payments"]] == ["1", "2"]
        assert item["payments"][0]["id"] < item["payments"][1]["id"]
    # Auth login/user, relógio, agregado, contagem, linhas e histórico em lote: sete SELECT.
    assert len(queries) <= 7


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/reports/aging?due_from=2026-08-18&due_to=2026-08-17",
        "/api/v1/reports/aging?bucket=91_plus",
        "/api/v1/reports/aging?as_of=2020-01-01",
        "/api/v1/reports/aging?page=10001",
        "/api/v1/reports/aging?customer_id=2147483648",
        "/api/v1/customers/1/statement?received_from=2026-08-18&received_to=2026-08-17",
        "/api/v1/customers/1/statement?status=typo",
        "/api/v1/customers/1/statement?status=",
        "/api/v1/customers/1/statement?as_of=2020-01-01",
        "/api/v1/customers/1/statement?payment_page=0",
    ],
)
def test_invalid_report_filters(client: TestClient, db: Session, path: str) -> None:
    customer(db)
    db.commit()
    login(client)
    assert client.get(path).status_code == 422
