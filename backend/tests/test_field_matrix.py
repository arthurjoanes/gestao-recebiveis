"Testa limites de entrada e efeitos no banco de testes."

import csv
import io
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_api import login
from test_financial import load

from gestao_recebiveis.import_csv import COLUMNS, MAX_BYTES, MAX_ROWS, parse
from gestao_recebiveis.imports import confirm_batch, create_preview
from gestao_recebiveis.models import AuditEvent, DemoState, Payment, Receivable
from gestao_recebiveis.receivables import pay
from gestao_recebiveis.reporting import overview, title_filters

BASE = [
    "manual",
    "M-1",
    "C-1",
    "Distribuição São José",
    "matriz@example.com",
    "Reposição de estoque",
    "10.20",
    "2026-08-17",
]


def export_row(values: list[str], *, bom: bool = False) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(COLUMNS)
    writer.writerow(values)
    return output.getvalue().encode("utf-8-sig" if bom else "utf-8")


@pytest.mark.parametrize("field,limit", [(0, 80), (1, 100), (2, 100), (3, 200), (5, 500)])
def test_csv_text_field_boundaries_reject_entire_batch(db: Session, field: int, limit: int) -> None:
    for value in ("", "   ", "á" * (limit + 1)):
        row = BASE.copy()
        row[field] = value
        batch = create_preview(db, "campos.csv", export_row(row), 1)
        assert batch.report["errors"]
        assert confirm_batch(db, batch.id, 1).status == "rejected"
    assert db.scalar(select(func.count(Receivable.id))) == 0
    row = BASE.copy()
    row[field] = "á" * limit
    batch = create_preview(db, "limite.csv", export_row(row), 1)
    assert not batch.report["errors"]
    assert confirm_batch(db, batch.id, 1).status == "confirmed"
    assert db.scalar(select(func.count(Receivable.id))) == 1


@pytest.mark.parametrize("value", ["", " ", "a@", "nome@example.com" + "x" * 254])
def test_invalid_email_is_diagnostic_and_atomic(db: Session, value: str) -> None:
    row = BASE.copy()
    row[4] = value
    batch = create_preview(db, "email.csv", export_row(row), 1)
    assert batch.report["errors"][0]["line"] == 2
    assert confirm_batch(db, batch.id, 1).status == "rejected"
    assert db.scalar(select(func.count(Receivable.id))) == 0


def test_trim_accents_bom_multiline_and_literal_search(db: Session) -> None:
    row = [f"  {value}  " for value in BASE]
    row[5] = '  Peças 10%_garantia\nSegunda linha "conferida"  '
    batch = create_preview(db, "unicode.csv", export_row(row, bom=True), 1)
    assert not batch.report["errors"]
    assert confirm_batch(db, batch.id, 1).status == "confirmed"
    title = db.scalar(select(Receivable))
    assert title and title.amount_cents == 1020
    assert title.description == 'Peças 10%_garantia\nSegunda linha "conferida"'
    for search in ["  São José  ", "10%_garantia", " "]:
        assert overview(db, search, None, None, None, None)["open_cents"] == "1020"
    assert overview(db, "11%_garantia", None, None, None, None)["open_cents"] == "0"
    # After a quoted newline, the next record begins on physical line 4.
    second = BASE.copy()
    second[7] = "2026-02-30"
    content = export_row(row) + export_row(second).split(b"\r\n", 1)[1]
    _, errors = parse(content)
    assert errors[0]["line"] == 4
    header, rest = content.split(b"\r\n", 1)
    _, errors = parse(header + b"\r\n\r\n" + rest)
    assert errors[0]["line"] == 5
    first = export_row(row)
    second_record = export_row(second).split(b"\r\n", 1)[1]
    _, errors = parse(first + b"\r\n" + second_record)
    assert errors[0]["line"] == 5


@pytest.mark.parametrize(
    "value,valid",
    [
        ("0001-01-01", True),
        ("9999-12-31", True),
        ("2028-02-29", True),
        ("2026-02-29", False),
        ("2026-13-01", False),
        ("2026-08-00", False),
        ("17/08/2026", False),
        ("2026-8-17", False),
        ("", False),
    ],
)
def test_csv_dates_are_calendar_dates(db: Session, value: str, valid: bool) -> None:
    row = BASE.copy()
    row[7] = value
    batch = create_preview(db, "datas.csv", export_row(row), 1)
    assert confirm_batch(db, batch.id, 1).status == ("confirmed" if valid else "rejected")
    assert db.scalar(select(func.count(Receivable.id))) == int(valid)


@pytest.mark.parametrize("content", [b"", b"\xff", b"\x00", b"a,b\n1,2", b"x" * (MAX_BYTES + 1)])
def test_invalid_file_envelope_never_yields_a_valid_record(content: bytes) -> None:
    rows, errors = parse(content)
    assert errors and not rows


def test_csv_record_limit_is_enforced_without_inserting_titles(db: Session) -> None:
    one = export_row(BASE)
    header, row = one.split(b"\r\n", 1)
    for count, valid in [(MAX_ROWS, True), (MAX_ROWS + 1, False)]:
        rows, errors = parse(header + b"\r\n" + row * count)
        assert bool(errors) is not valid
        assert len(rows) == MAX_ROWS
    assert db.scalar(select(func.count(Receivable.id))) == 0


def test_open_decomposition_includes_today_and_preserves_independent_receipts(db: Session) -> None:
    load(db)  # 1 cent yesterday, 10 cents today, 1020 cents tomorrow.
    totals = overview(db, "", None, None, None, None)
    assert {
        key: totals[key]
        for key in [
            "open_cents",
            "overdue_cents",
            "current_cents",
            "open_count",
            "overdue_count",
            "current_count",
        ]
    } == {
        "open_cents": "1031",
        "overdue_cents": "1",
        "current_cents": "1030",
        "open_count": 3,
        "overdue_count": 1,
        "current_count": 2,
    }
    current_ids = db.scalars(
        select(Receivable.external_receivable_id)
        .where(*title_filters("", "current", None, None, date(2026, 8, 17)))
        .order_by(Receivable.id)
    ).all()
    assert current_ids == ["B", "C"]
    pay(db, 1, "matrix-integral-payment", "Conferência", 1)
    only_today = overview(db, "", date(2026, 8, 17), date(2026, 8, 17), date.min, date.max)
    assert (
        only_today["open_cents"],
        only_today["current_cents"],
        only_today["overdue_cents"],
        only_today["received_cents"],
    ) == ("10", "10", "0", "1")
    no_receipts = overview(db, "", date.min, date.max, date(2026, 8, 18), date.max)
    assert (
        no_receipts["open_cents"],
        no_receipts["current_cents"],
        no_receipts["received_cents"],
    ) == ("1030", "1030", "0")


@pytest.mark.parametrize(
    "suffix",
    ["0", "-1", "2147483648", "9223372036854775808", "999999999999999999999999", "invalid"],
)
def test_resource_identifiers_reject_outside_database_range(
    client: TestClient, suffix: str
) -> None:
    login(client)
    for resource in ("receivables", "imports", "reminders"):
        response = client.get(f"/api/v1/{resource}/{suffix}")
        assert response.status_code == 422, response.text
    assert client.get("/api/v1/receivables/2147483647").status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"idempotency_key": "short"},
        {"idempotency_key": " " * 10},
        {"idempotency_key": "x" * 101},
        {"idempotency_key": "matrix-key", "note": "x" * 501},
        {"idempotency_key": "matrix-key", "amount_cents": "1"},
        {"idempotency_key": "matrix-key", "amount_brl": "0.01"},
        {"idempotency_key": "matrix-key", "note": None},
    ],
)
def test_invalid_or_partial_payment_has_no_financial_effect(
    client: TestClient, db: Session, payload: dict[str, Any]
) -> None:
    load(db)
    db.commit()
    headers = login(client)
    before = client.get("/api/v1/overview").json()
    response = client.post("/api/v1/receivables/3/payments", json=payload, headers=headers)
    assert response.status_code == 422, response.text
    assert client.get("/api/v1/overview").json() == before
    assert db.scalar(select(func.count(Payment.id))) == 0
    assert (
        db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.type == "payment_recorded"))
        == 0
    )


def test_integral_payment_accepts_boundaries_and_replays_trimmed_note(
    client: TestClient, db: Session
) -> None:
    load(db)
    db.commit()
    headers = login(client)
    payload = {"idempotency_key": "x" * 100, "note": "  " + "á" * 500 + "  "}
    first = client.post("/api/v1/receivables/3/payments", json=payload, headers=headers)
    assert first.status_code == 200
    assert first.json()["amount_cents"] == "1020"
    payload["note"] = payload["note"].strip()
    repeated = client.post("/api/v1/receivables/3/payments", json=payload, headers=headers)
    assert repeated.json() == first.json()
    assert db.scalar(select(func.count(Payment.id))) == 1


@pytest.mark.parametrize("reason", ["", "  ", "a", "ab", "  ab  ", "a" * 501])
def test_invalid_cancellation_preserves_open_title(
    client: TestClient, db: Session, reason: str
) -> None:
    load(db)
    db.commit()
    headers = login(client)
    assert (
        client.post(
            "/api/v1/receivables/1/cancel", json={"reason": reason}, headers=headers
        ).status_code
        == 422
    )
    assert client.get("/api/v1/receivables/1").json()["status"] == "open"


@pytest.mark.parametrize("value", ["false", "true", 0, 1, None])
def test_worker_requires_explicit_json_boolean(client: TestClient, db: Session, value: Any) -> None:
    headers = login(client)
    assert (
        client.post("/api/v1/demo/worker", json={"enabled": value}, headers=headers).status_code
        == 422
    )
    assert db.get(DemoState, 1).worker_enabled is False


@pytest.mark.parametrize(
    "value",
    [
        "",
        "2026-08-17T10:00:00",
        "2026-08-17T10:00:00-03:00",
        "1899-12-31T10:00:00-03:00",
        "2200-01-01T10:00:00-03:00",
        "9999-12-31T10:00:00-03:00",
        "2026-02-30T10:00:00-03:00",
    ],
)
def test_invalid_clock_does_not_advance_state(client: TestClient, value: str) -> None:
    headers = login(client)
    before = client.get("/api/v1/demo").json()
    assert (
        client.post("/api/v1/demo/clock", json={"business_now": value}, headers=headers).status_code
        == 422
    )
    assert client.get("/api/v1/demo").json() == before


@pytest.mark.parametrize(
    "params",
    [
        {"due_from": "2026-08-18", "due_to": "2026-08-17"},
        {"received_from": "2026-08-18", "received_to": "2026-08-17"},
        {"due_from": "0000-01-01"},
        {"due_to": "10000-01-01"},
        {"received_from": "2026-02-30"},
    ],
)
def test_overview_invalid_period_returns_422_without_mutation(
    client: TestClient, db: Session, params: dict[str, str]
) -> None:
    load(db)
    db.commit()
    login(client)
    before = client.get("/api/v1/overview").json()
    assert client.get("/api/v1/overview", params=params).status_code == 422
    assert client.get("/api/v1/overview").json() == before
