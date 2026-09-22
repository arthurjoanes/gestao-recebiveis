"""Domain and data proof for compose.restore-proof.yaml, never for the demo database.

The existing persistence_probe.py remains unchanged. This probe never truncates,
seeds or drops a database. Raw snapshots are written only to the private /evidence mount.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from restore_support import (
    FIXTURE,
    Contract,
    ProofRejected,
    canonical,
    csv_fixture,
    normalized,
    public_snapshot,
    require,
    write_private,
)

EVIDENCE = Path("/evidence")


def contract_from_environment() -> Contract:
    contract = Contract(
        os.environ.get("CF_RESTORE_RUN_ID", ""), os.environ.get("CF_RESTORE_ROLE", "")
    )
    contract.validate_environment(dict(os.environ))
    require(
        os.environ.get("CF_RESTORE_EVIDENCE_DIR") == "/evidence",
        "Evidence directory must be the private proof mount",
    )
    return contract


def load_private(name: str) -> dict:
    require(
        name in ("fixture", "cut", "source-cut", "restored-before-replay"),
        "Private input name rejected",
    )
    return json.loads((EVIDENCE / f"{name}.private.json").read_bytes())


def snapshot() -> dict:
    from gestao_recebiveis.database import engine
    from gestao_recebiveis.models import Base
    from sqlalchemy import text

    state = {"tables": {}, "sequences": {}}
    with engine.connect() as connection:
        with connection.begin():
            connection.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            observed_at = connection.scalar(text("SELECT clock_timestamp()"))
            version = connection.scalar(text("SHOW server_version"))
            names = connection.scalars(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
            ).all()
            expected = {*Base.metadata.tables, "alembic_version"}
            require(set(names) == expected, "Snapshot table inventory differs from local schema")
            quote = connection.dialect.identifier_preparer.quote
            for name in names:
                rows = connection.execute(text(f"SELECT * FROM public.{quote(name)}")).mappings()
                state["tables"][name] = sorted(
                    [normalized(dict(row)) for row in rows], key=canonical
                )
            sequences = connection.scalars(
                text(
                    "SELECT sequencename FROM pg_sequences WHERE schemaname='public' "
                    "ORDER BY sequencename"
                )
            ).all()
            for name in sequences:
                row = (
                    connection.execute(
                        text(f"SELECT last_value,is_called FROM public.{quote(name)}")
                    )
                    .mappings()
                    .one()
                )
                state["sequences"][name] = dict(row)
    return {"observed_at_utc": observed_at.isoformat(), "postgres_version": version, "state": state}


def save_snapshot(name: str) -> dict:
    value = snapshot()
    path = write_private(EVIDENCE, name, value)
    return {
        **public_snapshot(value),
        "private_file": path.name,
        "private_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def empty_destination(contract: Contract) -> dict:
    from gestao_recebiveis.database import engine
    from sqlalchemy import text

    require(contract.role == "dst", "Only destination can receive a restore")
    with engine.connect() as connection:
        count = connection.scalar(
            text(
                "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid "
                "WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S','f')"
            )
        )
    require(count == 0, "Destination is occupied; restore rejected before pg_restore")
    return {"public_schema_objects": 0, "empty": True}


def initialize(contract: Contract) -> dict:
    from gestao_recebiveis.auth import password_hasher
    from gestao_recebiveis.database import SessionLocal
    from gestao_recebiveis.imports import confirm_batch, create_preview
    from gestao_recebiveis.models import DemoState, Receivable, User
    from sqlalchemy import select

    require(contract.role == "src", "Fixture may only be created in source")
    before = snapshot()
    require(
        all(
            not rows
            for name, rows in before["state"]["tables"].items()
            if name != "alembic_version"
        ),
        "Fixture requires empty application tables",
    )
    password = os.environ.get("CF_RESTORE_OPERATOR_PASSWORD", "")
    require(len(password) >= 24, "Synthetic operator credential is missing")
    with SessionLocal.begin() as session:
        user = User(
            email=FIXTURE["operator_email"],
            name="Operador sintético do restore",
            role="operator",
            is_demo=True,
            password_hash=password_hasher.hash(password),
        )
        session.add(user)
        session.add(
            DemoState(
                id=1,
                business_now=datetime.fromisoformat(FIXTURE["business_now"]),
                worker_enabled=False,
            )
        )
        session.flush()
        batch = create_preview(session, "restore-two-titles.csv", csv_fixture(), user.id)
        require(
            confirm_batch(session, batch.id, user.id).status == "confirmed", "Fixture import failed"
        )
        titles = session.scalars(select(Receivable).order_by(Receivable.id)).all()
        require(
            {r.external_receivable_id: r.amount_cents for r in titles} == FIXTURE["titles"],
            "Fixture totals/identities differ",
        )
        fixture = {
            "run_id": contract.run_id,
            "actor_id": user.id,
            "batch_id": batch.id,
            "title_ids": {r.external_receivable_id: r.id for r in titles},
            "payment_key": f"restore-{contract.run_id}-payment",
            "payment_note": FIXTURE["payment_note"],
        }
    write_private(EVIDENCE, "fixture", fixture)
    return {
        "batch_id": fixture["batch_id"],
        "title_ids": fixture["title_ids"],
        "snapshot": save_snapshot("source-imported"),
    }


def conflict(contract: Contract) -> dict:
    from gestao_recebiveis.database import SessionLocal
    from gestao_recebiveis.imports import confirm_batch, create_preview

    require(contract.role == "src", "Conflict fixture is source-only")
    fixture = load_private("fixture")
    require(fixture["run_id"] == contract.run_id, "Fixture run mismatch")
    before = snapshot()
    with SessionLocal.begin() as session:
        repeated = create_preview(
            session, "restore-identical-repeat.csv", csv_fixture(), fixture["actor_id"]
        )
        repeated = confirm_batch(session, repeated.id, fixture["actor_id"])
        require(
            repeated.status == "confirmed"
            and repeated.report["existing_count"] == 2
            and repeated.report["new_count"] == 0,
            "Identical import was not idempotent",
        )
        repeated_id = repeated.id
    after_repeat = snapshot()
    for name in ("customers", "receivables", "payments"):
        require(
            before["state"]["tables"][name] == after_repeat["state"]["tables"][name],
            "Repeated import changed financial rows",
        )
    write_private(EVIDENCE, "identical-repeat-before", before)
    write_private(EVIDENCE, "identical-repeat-after", after_repeat)
    with SessionLocal.begin() as session:
        batch = create_preview(
            session, "restore-conflict-and-new.csv", csv_fixture(conflict=True), fixture["actor_id"]
        )
        confirmed = confirm_batch(session, batch.id, fixture["actor_id"])
        require(confirmed.status == "rejected", "Conflicting import was not rejected")
        require(
            any(error["code"] == "existing_conflict" for error in confirmed.report["errors"]),
            "Import rejection did not exercise an existing-title conflict",
        )
        batch_id = batch.id
    after = snapshot()
    for name in ("customers", "receivables", "payments"):
        require(
            before["state"]["tables"][name] == after["state"]["tables"][name],
            "Rejected import changed financial rows",
        )
    write_private(EVIDENCE, "conflict-before", before)
    write_private(EVIDENCE, "conflict-after", after)
    return {
        "batch_id": batch_id,
        "status": "rejected",
        "financial_rows_equal": True,
        "identical_repeat": {
            "batch_id": repeated_id,
            "new_count": 0,
            "existing_count": 2,
            "financial_rows_equal": True,
        },
        "candidate_total_cents": 15000,
        "actual_total_cents": 12500,
        "new_title_absent": True,
        "snapshot": public_snapshot(after),
        "allowed_change": "Rejected batch/lines/audit and consumed sequence values remain evidence",
    }


def prepare_cut(contract: Contract) -> dict:
    from gestao_recebiveis.database import SessionLocal
    from gestao_recebiveis.models import Attempt, Delivery, DemoState, Payment, Receivable, Reminder
    from gestao_recebiveis.receivables import pay
    from gestao_recebiveis.reminders.provider import FakeProvider, ResponseLost
    from gestao_recebiveis.reminders.service import authorize, claim, schedule
    from sqlalchemy import func, select

    require(contract.role == "src", "Cut fixture is source-only")
    fixture = load_private("fixture")
    require(fixture["run_id"] == contract.run_id, "Fixture run mismatch")
    with SessionLocal.begin() as session:
        payment = pay(
            session,
            fixture["title_ids"]["RESTORE-PAID"],
            fixture["payment_key"],
            fixture["payment_note"],
            fixture["actor_id"],
        )
        require(payment.amount_cents == 5000, "Payment oracle mismatch")
        payment_id = payment.id
        title = session.get(Receivable, fixture["title_ids"]["RESTORE-UNKNOWN"])
        title.scenario = "response_lost"
        session.get(DemoState, 1).worker_enabled = True
        require(schedule(session) == 1, "Exactly one unpaid reminder must be scheduled")
    with SessionLocal.begin() as session:
        possession = claim(session)
        require(
            possession is not None and possession.receivable_id == title.id,
            "Claimed unexpected reminder",
        )
    with SessionLocal.begin() as session:
        attempt = authorize(session, possession)
        require(attempt is not None, "Attempt authorization failed")
        attempt_id = attempt.id
    try:
        FakeProvider(SessionLocal).send(attempt_id)
    except ResponseLost:
        pass
    else:
        raise ProofRejected("Expected response loss after provider commit")
    with SessionLocal() as session:
        require(session.get(Attempt, attempt_id).outcome == "unknown", "Attempt not uncertain")
        require(
            session.get(Reminder, possession.reminder_id).status == "processing",
            "Reminder not left in-flight",
        )
        require(session.scalar(select(func.count(Delivery.id))) == 1, "Delivery ledger mismatch")
        require(session.scalar(select(func.count(Payment.id))) == 1, "Payment count mismatch")
        delivery_id = session.scalar(select(Delivery.id))
    cut = {
        "run_id": contract.run_id,
        "payment_id": payment_id,
        "delivery_id": delivery_id,
        "attempt_id": attempt_id,
        "reminder_id": possession.reminder_id,
        "receivable_id": possession.receivable_id,
        "old_token": possession.token,
        "failure": "FakeProvider ResponseLost after delivery/result commit; finish deliberately not called",
    }
    write_private(EVIDENCE, "cut", cut)
    return cut


def verify_roles() -> dict:
    from gestao_recebiveis.database import engine
    from gestao_recebiveis.models import Base
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    with engine.connect() as connection:
        require(
            connection.scalar(text("SELECT current_user")) == "gestao_app", "Wrong runtime role"
        )
        flags = connection.execute(
            text(
                "SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
                "FROM pg_roles WHERE rolname=current_user"
            )
        ).one()
        require(not any(flags), "Runtime role has administrative privileges")
        require(
            not connection.scalar(
                text("SELECT has_schema_privilege(current_user,'public','CREATE')")
            ),
            "Runtime can create schema objects",
        )
        require(
            not connection.scalar(text("SELECT pg_has_role(current_user,'gestao_owner','MEMBER')")),
            "Runtime can become owner",
        )
        for kind in ("CREATE", "TEMPORARY"):
            require(
                not connection.scalar(
                    text("SELECT has_database_privilege(current_user,current_database(),:kind)"),
                    {"kind": kind},
                ),
                "Runtime has database creation privilege",
            )
        require(
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner<>'gestao_owner'"
                )
            )
            == 0,
            "Restored tables have wrong owner",
        )
        require(
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_sequences WHERE schemaname='public' AND sequenceowner<>'gestao_owner'"
                )
            )
            == 0,
            "Restored sequences have wrong owner",
        )
        for table in Base.metadata.tables:
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                require(
                    connection.scalar(
                        text("SELECT has_table_privilege(current_user,:table,:privilege)"),
                        {"table": table, "privilege": privilege},
                    ),
                    "Missing runtime table grant",
                )
            require(
                not connection.scalar(
                    text("SELECT has_table_privilege(current_user,:table,'TRUNCATE')"),
                    {"table": table},
                ),
                "Runtime unexpectedly has truncate",
            )
        for sequence in connection.scalars(
            text("SELECT sequencename FROM pg_sequences WHERE schemaname='public'")
        ):
            for privilege in ("USAGE", "SELECT"):
                require(
                    connection.scalar(
                        text("SELECT has_sequence_privilege(current_user,:sequence,:privilege)"),
                        {"sequence": sequence, "privilege": privilege},
                    ),
                    "Missing sequence grant",
                )
    denied = []
    for label, statement in (
        ("create_table", "CREATE TABLE public.restore_forbidden_probe(id integer)"),
        ("set_owner_role", "SET ROLE gestao_owner"),
        ("write_schema_version", "UPDATE alembic_version SET version_num=version_num"),
    ):
        try:
            with engine.begin() as connection:
                connection.exec_driver_sql(statement)
                raise ProofRejected("Forbidden runtime privilege unexpectedly succeeded")
        except DBAPIError as error:
            require(
                getattr(error.orig, "sqlstate", None) == "42501",
                "Privilege failed for another reason",
            )
            denied.append(label)
    return {
        "runtime": "gestao_app",
        "owner": "gestao_owner",
        "administrative_flags": False,
        "ownership_and_required_grants": True,
        "denied_sql": denied,
    }


def replay_payment(contract: Contract) -> dict:
    from gestao_recebiveis.database import SessionLocal
    from gestao_recebiveis.errors import DomainError
    from gestao_recebiveis.receivables import pay

    require(contract.role == "dst", "Replay must run on destination")
    fixture, cut = load_private("fixture"), load_private("cut")
    require(fixture["run_id"] == cut["run_id"] == contract.run_id, "Replay run mismatch")
    before = snapshot()
    with SessionLocal.begin() as session:
        payment = pay(
            session,
            fixture["title_ids"]["RESTORE-PAID"],
            fixture["payment_key"],
            fixture["payment_note"],
            fixture["actor_id"],
        )
        require(
            payment.id == cut["payment_id"] and payment.amount_cents == 5000,
            "Replay created/returned a different payment",
        )
    try:
        with SessionLocal.begin() as session:
            pay(
                session,
                fixture["title_ids"]["RESTORE-PAID"],
                fixture["payment_key"],
                "Conteúdo diferente deve conflitar",
                fixture["actor_id"],
            )
    except DomainError as error:
        require(error.code == "idempotency_conflict", "Wrong payment rejection reason")
    else:
        raise ProofRejected("Changed payment content was accepted")
    after = snapshot()
    require(before["state"] == after["state"], "Payment replay/conflict changed persisted state")
    write_private(EVIDENCE, "payment-replay-before", before)
    write_private(EVIDENCE, "payment-replay-after", after)
    return {
        "same_payment_id": cut["payment_id"],
        "same_complete_state": True,
        "conflict_code": "idempotency_conflict",
        "snapshot": public_snapshot(after),
    }


def reconcile(contract: Contract) -> dict:
    from gestao_recebiveis.database import SessionLocal
    from gestao_recebiveis.reminders.provider import FakeProvider, SendResult
    from gestao_recebiveis.reminders.service import Claim, authorize, claim, finish, renew

    require(contract.role == "dst", "Reconciliation must run on destination")
    cut = load_private("cut")
    require(cut["run_id"] == contract.run_id, "Reconciliation run mismatch")
    before = snapshot()
    old = Claim(cut["reminder_id"], cut["receivable_id"], cut["old_token"])
    deadline = time.monotonic() + FIXTURE["lease_recovery_deadline_seconds"]
    possession = None
    while possession is None and time.monotonic() < deadline:
        with SessionLocal.begin() as session:
            possession = claim(session)
        require(time.monotonic() < deadline, "Lease claim completed after recovery deadline")
        if possession is None:
            time.sleep(0.1)
    require(
        possession is not None
        and possession.reminder_id == old.reminder_id
        and possession.token > old.token,
        "Real lease was not recovered for the same reminder",
    )
    with SessionLocal.begin() as session:
        require(not renew(session, old), "Old owner renewed after fencing")
        require(
            not finish(session, old, cut["attempt_id"], SendResult("permanent", "late owner")),
            "Old owner finalized after fencing",
        )
        attempt = authorize(session, possession)
        require(
            attempt is not None and attempt.id == cut["attempt_id"], "A second attempt was created"
        )
    result = FakeProvider(SessionLocal).send(cut["attempt_id"])
    require(result.outcome == "success", "Stored fake-provider result not recovered")
    with SessionLocal.begin() as session:
        require(
            finish(session, possession, cut["attempt_id"], result), "Current owner did not finish"
        )
    after = snapshot()
    old_tables, new_tables = before["state"]["tables"], after["state"]["tables"]
    changed = {"reminders", "attempts", "audit_events"}
    for name in set(old_tables) - changed:
        require(
            old_tables[name] == new_tables[name], f"Reconciliation changed invariant table {name}"
        )
    for table, allowed in (
        ("attempts", {"outcome", "finished_at", "error"}),
        ("reminders", {"status", "lease_token", "lease_expires_at", "last_error"}),
    ):
        require(
            len(old_tables[table]) == len(new_tables[table]) == 1, "Attempt/reminder count changed"
        )
        previous, current = old_tables[table][0], new_tables[table][0]
        require(
            {k: v for k, v in previous.items() if k not in allowed}
            == {k: v for k, v in current.items() if k not in allowed},
            f"Unexpected reconciliation mutation in {table}",
        )
    require(
        new_tables["attempts"][0]["outcome"] == "success"
        and new_tables["reminders"][0]["status"] == "sent",
        "Reconciliation terminal states differ",
    )
    original_events = {row["id"]: row for row in old_tables["audit_events"]}
    final_events = {row["id"]: row for row in new_tables["audit_events"]}
    require(
        all(final_events.get(key) == row for key, row in original_events.items()),
        "Existing audit history changed",
    )
    appended = [row for key, row in final_events.items() if key not in original_events]
    require(
        sorted(row["type"] for row in appended) == ["reminder.reconciling", "reminder.sent"],
        "Unexpected reconciliation audit events",
    )
    sequences_before, sequences_after = before["state"]["sequences"], after["state"]["sequences"]
    require(sequences_before.keys() == sequences_after.keys(), "Sequence inventory changed")
    for name, previous in sequences_before.items():
        current = sequences_after[name]
        require(
            current["last_value"] >= previous["last_value"]
            and (not previous["is_called"] or current["is_called"]),
            "Sequence moved backwards",
        )
    write_private(EVIDENCE, "reconciliation-before", before)
    write_private(EVIDENCE, "reconciliation-after", after)
    return {
        "same_attempt_id": cut["attempt_id"],
        "same_reminder_id": cut["reminder_id"],
        "old_token": old.token,
        "new_token": possession.token,
        "old_owner_rejected": True,
        "same_payments_deliveries_provider_results": True,
        "appended_audit_types": [row["type"] for row in appended],
        "sequence_changes": {
            name: {"before": sequences_before[name], "after": value}
            for name, value in sequences_after.items()
            if sequences_before[name] != value
        },
        "sequence_limit": "INSERT ON CONFLICT can consume a sequence value without a new row",
        "snapshot": public_snapshot(after),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase",
        choices=(
            "initialize",
            "conflict",
            "cut",
            "snapshot",
            "assert-empty",
            "verify-roles",
            "replay",
            "reconcile",
        ),
    )
    parser.add_argument("--name")
    args = parser.parse_args()
    # Guard before importing the application's engine or opening any connection.
    contract = contract_from_environment()
    phase = args.phase
    if phase == "snapshot":
        require(bool(args.name), "Snapshot requires an explicit evidence name")
        result = save_snapshot(args.name)
    else:
        handlers = {
            "initialize": initialize,
            "conflict": conflict,
            "cut": prepare_cut,
            "assert-empty": empty_destination,
            "replay": replay_payment,
            "reconcile": reconcile,
        }
        result = verify_roles() if phase == "verify-roles" else handlers[phase](contract)
    print(
        json.dumps(
            {
                "recorded_at": datetime.now(UTC).isoformat(),
                "phase": phase,
                "role": contract.role,
                "result": result,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except ProofRejected as error:
        print(json.dumps({"status": "rejected", "reason": str(error)}))
        raise SystemExit(2) from None
