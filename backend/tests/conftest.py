from collections.abc import Iterator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from gestao_recebiveis.auth import password_hasher
from gestao_recebiveis.config import get_settings
from gestao_recebiveis.database import SessionLocal, engine
from gestao_recebiveis.models import Base, DemoState, User


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    if not engine.url.database or not engine.url.database.endswith("_test"):
        raise RuntimeError("Testes destrutivos exigem banco com sufixo _test.")
    names = ", ".join('"' + table.name + '"' for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    yield SessionLocal


@pytest.fixture(autouse=True)
def bootstrap(session_factory: sessionmaker[Session]) -> None:
    with session_factory.begin() as session:
        hashed = password_hasher.hash("Recebiveis!2026")
        session.add_all(
            [
                User(
                    email="operador@example.com",
                    name="Operador",
                    role="operator",
                    password_hash=hashed,
                ),
                User(
                    email="leitor@example.com", name="Leitor", role="reader", password_hash=hashed
                ),
                DemoState(
                    id=1,
                    business_now=datetime.fromisoformat("2026-08-17T10:00:00-03:00"),
                    worker_enabled=False,
                ),
            ]
        )


@pytest.fixture
def db(session_factory: sessionmaker[Session], bootstrap: None) -> Iterator[Session]:
    with session_factory() as session:
        yield session


@pytest.fixture
def operator(db: Session) -> User:
    user = db.get(User, 1)
    assert user
    return user


@pytest.fixture
def client() -> Iterator[TestClient]:
    from gestao_recebiveis.app import app

    with TestClient(app, base_url=get_settings().frontend_origin) as test_client:
        yield test_client
