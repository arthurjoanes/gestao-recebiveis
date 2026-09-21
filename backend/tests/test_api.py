from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_financial import HEADER, LINES

from gestao_recebiveis.clock import utcnow
from gestao_recebiveis.config import get_settings
from gestao_recebiveis.models import LoginSession


def login(client: TestClient, role: str = "operador") -> dict[str, str]:
    origin = get_settings().frontend_origin
    response = client.post(
        "/api/v1/auth/login",
        json={"email": f"{role}@example.com", "password": "Recebiveis!2026"},
        headers={"Origin": origin},
    )
    assert response.status_code == 200, response.text
    assert "HttpOnly" in response.headers["set-cookie"]
    return {"Origin": origin, "X-CSRF-Token": response.json()["csrf_token"]}


def test_api_vertical_flow(client: TestClient) -> None:
    headers = login(client)
    preview = client.post(
        "/api/v1/imports",
        headers=headers,
        files={"file": ("valid.csv", (HEADER + "".join(LINES)).encode(), "text/csv")},
    )
    assert preview.status_code == 200, preview.text
    batch = preview.json()
    assert batch["report"]["total_cents"] == "1031"
    result = client.post(f"/api/v1/imports/{batch['id']}/confirm", headers=headers)
    assert result.json()["status"] == "confirmed"
    titles = client.get("/api/v1/receivables?q=Centavo").json()
    assert titles["total"] == 2
    item = titles["items"][0]
    payment = client.post(
        f"/api/v1/receivables/{item['id']}/payments",
        headers=headers,
        json={"idempotency_key": "api-payment-test", "note": ""},
    )
    assert payment.status_code == 200, payment.text
    detail = client.get(f"/api/v1/receivables/{item['id']}").json()
    assert detail["status"] == "paid"
    assert any(event["type"] == "payment_recorded" for event in detail["events"])
    assert client.get("/api/v1/overview").json()["received_cents"] == "1"


def test_reader_cannot_mutate(client: TestClient) -> None:
    headers = login(client, "leitor")
    checks = [
        ("/api/v1/receivables/1/payments", {"idempotency_key": "reader-payment"}),
        ("/api/v1/receivables/1/cancel", {"reason": "teste"}),
        ("/api/v1/imports/1/confirm", {}),
        ("/api/v1/demo/clock", {"business_now": "2026-08-18T10:00:00-03:00"}),
        ("/api/v1/demo/worker", {"enabled": True}),
        ("/api/v1/demo/scenario", {"receivable_id": 1, "scenario": "success"}),
    ]
    for path, payload in checks:
        assert client.post(path, json=payload, headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/imports", headers=headers, files={"file": ("a.csv", HEADER.encode())}
        ).status_code
        == 403
    )
    assert client.get("/api/v1/overview").status_code == 200


def test_csrf_origin_logout_and_session_expiry(client: TestClient, db: Session) -> None:
    assert client.get("/api/v1/auth/session").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "operador@example.com", "password": "Recebiveis!2026"},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    headers = login(client)
    assert client.post("/api/v1/demo/worker", json={"enabled": True}).status_code == 403
    assert (
        client.post(
            "/api/v1/demo/worker",
            json={"enabled": True},
            headers={**headers, "Origin": "http://localhost:3102"},
        ).status_code
        == 403
    )
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/session").status_code == 401
    login(client)
    session = db.scalar(select(LoginSession))
    assert session
    session.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert client.get("/api/v1/auth/session").status_code == 401


def test_demo_clock_does_not_expire_session(client: TestClient) -> None:
    headers = login(client)
    assert (
        client.post(
            "/api/v1/demo/clock",
            json={"business_now": "2030-01-01T10:00:00-03:00"},
            headers=headers,
        ).status_code
        == 200
    )
    assert client.get("/api/v1/auth/session").status_code == 200
    assert (
        client.post(
            "/api/v1/demo/clock",
            json={"business_now": "2020-01-01T10:00:00-03:00"},
            headers=headers,
        ).status_code
        == 422
    )


def test_demo_disabled_rejects_controls(client: TestClient) -> None:
    headers = login(client)
    settings = get_settings()
    previous = settings.demo_mode
    settings.demo_mode = False
    try:
        assert (
            client.post("/api/v1/demo/worker", json={"enabled": True}, headers=headers).status_code
            == 403
        )
    finally:
        settings.demo_mode = previous


def test_upload_limit_before_multipart_parser(client: TestClient) -> None:
    from gestao_recebiveis.request_limits import MAX_REQUEST_BYTES

    headers = login(client)
    content = b"x" * (MAX_REQUEST_BYTES + 1)
    assert client.post("/api/v1/imports", headers=headers, content=content).status_code == 413
    streamed = (content[index : index + 65536] for index in range(0, len(content), 65536))
    assert client.post("/api/v1/imports", headers=headers, content=streamed).status_code == 413


def test_demo_accounts_and_old_sessions_blocked_outside_demo(
    client: TestClient, db: Session
) -> None:
    from gestao_recebiveis.models import User

    user = db.get(User, 1)
    assert user
    user.is_demo = True
    db.commit()
    login(client)
    settings = get_settings()
    settings.demo_mode = False
    try:
        assert client.get("/api/v1/auth/session").status_code == 401
        response = client.post(
            "/api/v1/auth/login",
            headers={"Origin": settings.frontend_origin},
            json={"email": "operador@example.com", "password": "Recebiveis!2026"},
        )
        assert response.status_code == 401
    finally:
        settings.demo_mode = True


def test_import_history_returns_only_summary_and_detail_preserves_report(
    client: TestClient,
) -> None:
    headers = login(client)
    preview = client.post(
        "/api/v1/imports",
        headers=headers,
        files={"file": ("history.csv", (HEADER + "".join(LINES)).encode(), "text/csv")},
    ).json()
    history = client.get("/api/v1/imports").json()
    assert history["items"] == [
        {
            "id": preview["id"],
            "filename": "history.csv",
            "status": "preview",
            "created_at": preview["created_at"],
            "row_count": 3,
        }
    ]
    detail = client.get(f"/api/v1/imports/{preview['id']}").json()
    assert detail["report"] == preview["report"]
    assert len(detail["report"]["rows"]) == 3


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/receivables?page=9999999999999999999999",
        "/api/v1/imports?page_size=101",
        "/api/v1/reminders?status=typo",
        "/api/v1/overview?q=" + "a" * 201,
    ],
)
def test_invalid_filters_return_validation_errors(client: TestClient, path: str) -> None:
    login(client)
    assert client.get(path).status_code == 422


def test_json_limit_rejects_declared_and_streamed_bodies_before_parsing(client: TestClient) -> None:
    from gestao_recebiveis.request_limits import MAX_JSON_BYTES

    content = b"x" * (MAX_JSON_BYTES + 1)
    for body in (content, iter([content[:4096], content[4096:]])):
        response = client.post("/api/v1/auth/login", content=body)
        assert response.status_code == 413
        assert response.json()["code"] == "request_too_large"
    assert client.get("/health").status_code == 200


def test_login_preserves_password_whitespace(client: TestClient, db: Session) -> None:
    from gestao_recebiveis.auth import password_hasher
    from gestao_recebiveis.models import User

    user = db.get(User, 1)
    assert user
    user.password_hash = password_hasher.hash(" Recebiveis!2026 ")
    db.commit()
    headers = {"Origin": get_settings().frontend_origin}
    for password, expected in [("Recebiveis!2026", 401), (" Recebiveis!2026 ", 200)]:
        response = client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={
                "email": " OPERADOR@EXAMPLE.COM ",
                "password": password,
            },
        )
        assert response.status_code == expected


def test_exhausted_database_pool_returns_recoverable_error(client: TestClient) -> None:
    from gestao_recebiveis.database import engine

    login(client)
    connections = [engine.connect() for _ in range(10)]
    try:
        response = client.get("/api/v1/overview")
        assert response.status_code == 503
        assert response.headers["Retry-After"] == "2"
        assert response.json()["code"] == "database_unavailable"
        assert "SELECT" not in response.text
    finally:
        for connection in connections:
            connection.close()
    assert client.get("/api/v1/overview").status_code == 200
