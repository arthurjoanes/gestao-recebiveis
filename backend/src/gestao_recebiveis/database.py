from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from gestao_recebiveis.config import get_settings

engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_timeout=5,
    connect_args={
        "connect_timeout": 5,
        "options": "-c statement_timeout=15000 -c lock_timeout=5000",
    },
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with SessionLocal.begin() as session:
        yield session


@contextmanager
def read_snapshot() -> Iterator[Session]:
    # A sessão de autenticação já consultou o banco. O snapshot precisa de uma
    # sessão própria, configurada antes da primeira consulta do relatório.
    with SessionLocal.begin() as session:
        session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        yield session


def get_read_session() -> Iterator[Session]:
    with read_snapshot() as session:
        yield session


ReadDb = Annotated[Session, Depends(get_read_session, scope="function")]
