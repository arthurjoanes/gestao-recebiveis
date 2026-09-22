from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from gestao_recebiveis import auth
from gestao_recebiveis.clock import utcnow
from gestao_recebiveis.config import get_settings
from gestao_recebiveis.database import SessionLocal
from gestao_recebiveis.errors import DomainError
from gestao_recebiveis.login_admission import ACCOUNT_LIMIT, admit_login, release_success
from gestao_recebiveis.models import LoginAdmission


def test_rejections_persist_and_stop_hashing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0
    original = auth.password_hasher.verify

    def verify(password: str, hashed: str) -> bool:
        nonlocal calls
        calls += 1
        return original(password, hashed)

    monkeypatch.setattr(auth.password_hasher, "verify", verify)
    headers = {"Origin": get_settings().frontend_origin}
    payload = {"email": "operador@example.com", "password": "invalid-test-password"}
    for _ in range(ACCOUNT_LIMIT):
        assert client.post("/api/v1/auth/login", json=payload, headers=headers).status_code == 401
    for _ in range(10):
        response = client.post("/api/v1/auth/login", json=payload, headers=headers)
        assert response.status_code == 429
        assert 1 <= int(response.headers["retry-after"]) <= 60
    assert calls == ACCOUNT_LIMIT
    # Rejected account does not consume source budget or lock another user out.
    payload = {"email": "leitor@example.com", "password": "Recebiveis!2026"}
    assert client.post("/api/v1/auth/login", json=payload, headers=headers).status_code == 200


def test_admission_atomic_across_connections_and_sources() -> None:
    def attempt(_: int) -> bool:
        try:
            admit_login("operador@example.com", "local-source-a")
            return True
        except DomainError as exc:
            assert exc.status == 429
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(16))) == ACCOUNT_LIMIT
    # Same account, independent source: no global account lock.
    admit_login("operador@example.com", "local-source-b")


def test_window_expiry_and_normalization(db: Session) -> None:
    for _ in range(ACCOUNT_LIMIT):
        admit_login(" Operador@Example.com ", "source")
    with pytest.raises(DomainError):
        admit_login("operador@example.com", "source")
    with SessionLocal.begin() as session:
        session.execute(update(LoginAdmission).values(window_start=utcnow() - timedelta(minutes=2)))
    admit_login("operador@example.com", "source")
    assert set(db.scalars(select(LoginAdmission.attempts))) == {1}


def test_many_accounts_share_source_budget_but_not_other_source() -> None:
    for i in range(30):
        admit_login(f"account-{i}@example.com", "source-a")
    with pytest.raises(DomainError) as error:
        admit_login("new-account@example.com", "source-a")
    assert error.value.status == 429
    admit_login("new-account@example.com", "source-b")


def test_forwarded_header_does_not_reset_admission(client: TestClient) -> None:
    for i in range(ACCOUNT_LIMIT + 1):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "operador@example.com", "password": "invalid-password"},
            headers={"Origin": get_settings().frontend_origin, "X-Forwarded-For": f"192.0.2.{i}"},
        )
    assert response.status_code == 429


def test_success_releases_only_its_reservation(client: TestClient) -> None:
    headers = {"Origin": get_settings().frontend_origin}
    for _ in range(8):
        assert (
            client.post(
                "/api/v1/auth/login",
                headers=headers,
                json={"email": "operador@example.com", "password": "Recebiveis!2026"},
            ).status_code
            == 200
        )
    with SessionLocal() as session:
        assert set(session.scalars(select(LoginAdmission.attempts))) == {0}


def test_rolled_back_login_does_not_release_admission() -> None:
    reservation = admit_login("operador@example.com", "rollback-source")
    with pytest.raises(RuntimeError):
        with SessionLocal.begin() as session:
            release_success(session, reservation)
            raise RuntimeError("simulated login transaction failure")
    with SessionLocal() as session:
        assert set(session.scalars(select(LoginAdmission.attempts))) == {1}
