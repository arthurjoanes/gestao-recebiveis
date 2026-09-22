"""Bound password hashing with durable, atomic PostgreSQL admission counters."""

import hashlib
import hmac
import math
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from gestao_recebiveis.config import get_settings
from gestao_recebiveis.database import SessionLocal
from gestao_recebiveis.errors import DomainError
from gestao_recebiveis.models import LoginAdmission

ACCOUNT_LIMIT = 5
SOURCE_LIMIT = 30
WINDOW_SECONDS = 60


def admission_key(value: str) -> str:
    # Store neither e-mail addresses nor network addresses in the counter table.
    return hmac.new(
        get_settings().session_secret.encode(), value.encode(), hashlib.sha256
    ).hexdigest()


def admit_login(email: str, source: str) -> list[tuple[str, datetime]]:
    pair_key = admission_key(f"account\0{source}\0{email.strip().lower()}")
    source_key = admission_key(f"source\0{source}")
    admitted: list[tuple[str, datetime]] = []
    rejected = False
    retry_after = WINDOW_SECONDS
    # Independent transaction: a 401 rolls back the login, never its admission.
    with SessionLocal.begin() as session:
        # Serialize only requests from this source across API workers/processes.
        lock = int(source_key[:16], 16) - (1 << 63)
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
        now = session.scalar(select(func.clock_timestamp()))
        assert now is not None
        start = now
        expires_before = now - timedelta(seconds=WINDOW_SECONDS)
        # Cleanup is bounded by the admitted workload; no unbounded identity history.
        session.execute(delete(LoginAdmission).where(LoginAdmission.window_start <= expires_before))
        for key, limit in ((pair_key, ACCOUNT_LIMIT), (source_key, SOURCE_LIMIT)):
            existing = session.get(LoginAdmission, key)
            if existing is not None and existing.attempts >= limit:
                rejected = True
                retry_after = max(
                    1,
                    math.ceil(
                        (
                            existing.window_start + timedelta(seconds=WINDOW_SECONDS) - now
                        ).total_seconds()
                    ),
                )
                break
        if not rejected:
            for key in (pair_key, source_key):
                existing = session.get(LoginAdmission, key)
                admitted.append((key, existing.window_start if existing else now))
                session.execute(
                    insert(LoginAdmission)
                    .values(key=key, window_start=start, attempts=1)
                    .on_conflict_do_update(
                        index_elements=[LoginAdmission.key],
                        set_={"attempts": LoginAdmission.attempts + 1},
                    )
                )
    if rejected:
        raise DomainError(
            "login_throttled",
            "Muitas tentativas de entrada. Aguarde antes de tentar novamente.",
            429,
            {"Retry-After": str(retry_after)},
        )

    return admitted


def release_success(session: Session, admitted: list[tuple[str, datetime]]) -> None:
    """Release this reservation only if the enclosing login transaction commits."""
    lock = int(admitted[1][0][:16], 16) - (1 << 63)
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
    for key, window in admitted:
        session.execute(
            update(LoginAdmission)
            .where(LoginAdmission.key == key, LoginAdmission.window_start == window)
            .values(attempts=func.greatest(0, LoginAdmission.attempts - 1))
        )
