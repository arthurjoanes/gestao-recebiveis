"""Interrupção após aceitação e recuperação no PostgreSQL descartável da prova."""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep

from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url

from gestao_recebiveis.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "verify"])
    phase = parser.parse_args().phase
    settings = get_settings()
    target = make_url(settings.database_url)
    if (
        target.host != "db"
        or target.database != "gestao_recebiveis_proof_test"
        or not settings.demo_mode
        or os.environ.get("CF_PROOF_MODE") != "isolated"
    ):
        raise SystemExit("Probe restrito a compose.proof.yaml/gestao_recebiveis_proof_test.")

    from gestao_recebiveis.auth import password_hasher
    from gestao_recebiveis.database import SessionLocal, engine
    from gestao_recebiveis.imports import confirm_batch, create_preview
    from gestao_recebiveis.models import (
        Attempt,
        Base,
        Delivery,
        DemoState,
        Receivable,
        Reminder,
        User,
    )
    from gestao_recebiveis.reminders.provider import FakeProvider, ResponseLost, SendResult
    from gestao_recebiveis.reminders.service import Claim, authorize, claim, finish, renew, schedule

    evidence = Path("/evidence")
    if phase == "prepare":
        with SessionLocal.begin() as session:
            names = ", ".join('"' + table.name + '"' for table in Base.metadata.sorted_tables)
            session.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
            session.add(
                User(
                    email="probe@example.com",
                    name="Operador fictício da prova",
                    role="operator",
                    password_hash=password_hasher.hash("Recebiveis!2026"),
                    is_demo=True,
                )
            )
            session.add(
                DemoState(
                    id=1,
                    business_now=datetime.fromisoformat("2026-08-17T10:00:00-03:00"),
                    worker_enabled=True,
                )
            )
            session.flush()
            content = b"source_system,external_receivable_id,external_customer_id,customer_name,customer_email,description,amount_brl,due_date\nprobe,PERSIST-001,C1,Cliente Ficticio Probe,probe@example.com,Prova de persistencia,0.31,2026-08-20\n"
            batch = create_preview(session, "probe.csv", content, 1)
            assert confirm_batch(session, batch.id, 1).status == "confirmed"
            title = session.get(Receivable, 1)
            assert title and title.amount_cents == 31
            title.scenario = "response_lost"
            assert schedule(session) == 1
        with SessionLocal.begin() as session:
            possession = claim(session)
            assert possession
        with SessionLocal.begin() as session:
            attempt = authorize(session, possession)
            assert attempt
            attempt_id = attempt.id
        try:
            FakeProvider(SessionLocal).send(attempt_id)
        except ResponseLost:
            pass
        else:
            raise AssertionError("A resposta deveria ser perdida após o commit da entrega.")
        with SessionLocal() as session:
            attempt = session.get(Attempt, attempt_id)
            job = session.get(Reminder, possession.reminder_id)
            assert attempt and attempt.outcome == "unknown"
            assert job and job.status == "processing"
            assert session.scalar(select(func.count(Delivery.id))) == 1
            snapshot = {
                "phase": phase,
                "observed_at_utc": datetime.now(UTC).isoformat(),
                "postgres_started_at": session.scalar(
                    text("SELECT pg_postmaster_start_time()")
                ).isoformat(),
                "postgres_version": session.scalar(text("SHOW server_version")),
                "reminder_id": job.id,
                "receivable_id": job.receivable_id,
                "old_token": possession.token,
                "attempt_id": attempt_id,
                "expected": {
                    "delivery_count": 1,
                    "attempt_count": 1,
                    "amount_cents": 31,
                    "outcome": "unknown",
                    "status": "processing",
                },
                "observed": {
                    "delivery_count": 1,
                    "attempt_count": session.scalar(select(func.count(Attempt.id))),
                    "amount_cents": session.get(Receivable, 1).amount_cents,
                    "outcome": attempt.outcome,
                    "status": job.status,
                },
                "termination": "os._exit(86), no finish, after provider transaction committed",
            }
        (evidence / "accepted-before-interruption.json").write_text(
            json.dumps(snapshot, indent=2), encoding="utf-8"
        )
        print(json.dumps(snapshot), flush=True)
        # Ponto de falha explícito: não executa finally nem finalização do worker.
        os._exit(86)

    before = json.loads(
        (evidence / "accepted-before-interruption.json").read_text(encoding="utf-8")
    )
    old = Claim(before["reminder_id"], before["receivable_id"], before["old_token"])
    with SessionLocal() as session:
        restarted_at = session.scalar(text("SELECT pg_postmaster_start_time()")).isoformat()
        assert restarted_at != before["postgres_started_at"], "PostgreSQL não foi reiniciado."
        assert session.scalar(select(func.count(Delivery.id))) == 1
    deadline = monotonic() + 15
    possession = None
    while possession is None and monotonic() < deadline:
        with SessionLocal.begin() as session:
            possession = claim(session)
        if possession is None:
            sleep(0.1)
    assert possession and possession.token > old.token, "Lease real não foi recuperado."
    with SessionLocal.begin() as session:
        assert not renew(session, old)
        assert not finish(
            session, old, before["attempt_id"], SendResult("permanent", "Resposta tardia")
        )
        attempt = authorize(session, possession)
        assert attempt and attempt.id == before["attempt_id"]
        attempt_id = attempt.id
    result = FakeProvider(SessionLocal).send(attempt_id)
    with SessionLocal.begin() as session:
        assert finish(session, possession, attempt_id, result)
    with SessionLocal() as session:
        job = session.get(Reminder, possession.reminder_id)
        attempt = session.get(Attempt, attempt_id)
        assert job and attempt
        observed = {
            "delivery_count": session.scalar(select(func.count(Delivery.id))),
            "attempt_count": session.scalar(select(func.count(Attempt.id))),
            "amount_cents": session.get(Receivable, old.receivable_id).amount_cents,
            "outcome": attempt.outcome,
            "status": job.status,
        }
    expected = {
        "delivery_count": 1,
        "attempt_count": 1,
        "amount_cents": 31,
        "outcome": "success",
        "status": "sent",
    }
    assert observed == expected
    snapshot = {
        "phase": phase,
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "postgres_started_at": restarted_at,
        "expected": expected,
        "observed": observed,
        "old_token": old.token,
        "new_token": possession.token,
        "old_owner_rejected": True,
        "clock": "real infrastructure time; no FixedClock",
        "result": "passed",
    }
    (evidence / "recovered-after-restart.json").write_text(
        json.dumps(snapshot, indent=2), encoding="utf-8"
    )
    print(json.dumps(snapshot))
    engine.dispose()


if __name__ == "__main__":
    main()
