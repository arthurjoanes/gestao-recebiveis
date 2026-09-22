"""Pure helpers for the isolated restore proof; no connection on import."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

MODE = "isolated-restore-v1"
FIXTURE = {
    "source_system": "restore-proof",
    "customer_external_id": "RESTORE-CUSTOMER",
    "operator_email": "restore.operator@example.com",
    "business_now": "2026-08-17T10:00:00-03:00",
    "due_date": "2026-08-20",
    "titles": {"RESTORE-PAID": 5000, "RESTORE-UNKNOWN": 7500},
    "total_cents": 12500,
    "payment_cents": 5000,
    "open_cents_at_cut": 7500,
    "payment_note": "Baixa sintética antes do backup.",
    "conflicting_import": {
        "RESTORE-PAID": 5100,
        "RESTORE-SHOULD-NOT-EXIST": 9900,
    },
    "lease_seconds": 3,
    "lease_recovery_deadline_seconds": 15,
    "provider": "FakeProvider with ProviderResult/Delivery in the same PostgreSQL",
}
CSV_HEADER = (
    "source_system,external_receivable_id,external_customer_id,customer_name,"
    "customer_email,description,amount_brl,due_date\n"
)


class ProofRejected(RuntimeError):
    """A contract or evidence check failed; do not mutate the target."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProofRejected(message)


@dataclass(frozen=True)
class Contract:
    run_id: str
    role: str

    def __post_init__(self) -> None:
        require(bool(re.fullmatch(r"[a-f0-9]{32}", self.run_id)), "Invalid restore run ID")
        require(self.role in ("src", "dst"), "Invalid restore role")

    @property
    def project(self) -> str:
        return f"pf-gr-restore-{self.role}-{self.run_id[:12]}"

    @property
    def database(self) -> str:
        return f"gr_restore_{self.run_id}_{self.role}_test"

    @property
    def labels(self) -> dict[str, str]:
        return {
            "com.portfolio.restore.run": self.run_id,
            "com.portfolio.restore.role": self.role,
            "com.portfolio.restore.purpose": MODE,
        }

    def validate_environment(self, env: dict[str, str]) -> None:
        require(env.get("CF_RESTORE_MODE") == MODE, "Restore mode rejected")
        require(env.get("CF_RESTORE_RUN_ID") == self.run_id, "Restore run binding rejected")
        require(env.get("CF_RESTORE_ROLE") == self.role, "Restore role binding rejected")
        require(env.get("CF_RESTORE_PROJECT") == self.project, "Restore project rejected")
        require(env.get("DEMO_MODE", "").lower() == "true", "Restore requires synthetic demo mode")
        self.validate_url(env.get("DATABASE_URL", ""), "gestao_app")

    def validate_url(self, value: str, user: str) -> None:
        try:
            target = urlsplit(value)
            valid = (
                target.scheme == "postgresql+psycopg"
                and target.hostname == "db"
                and target.port == 5432
                and target.username == user
                and target.path == "/" + self.database
                and not target.query
                and not target.fragment
            )
        except ValueError:
            valid = False
        require(valid, "Database URL is outside the isolated restore contract")


def csv_fixture(*, conflict: bool = False) -> bytes:
    values = FIXTURE["conflicting_import"] if conflict else FIXTURE["titles"]
    rows = []
    for external_id, cents in values.items():
        rows.append(
            f"restore-proof,{external_id},RESTORE-CUSTOMER,Cliente Sintetico Restore,"
            f"restore.customer@example.com,Titulo sintetico {external_id},"
            f"{cents // 100}.{cents % 100:02d},2026-08-20\n"
        )
    return (CSV_HEADER + "".join(rows)).encode()


def normalized(value):
    if isinstance(value, (datetime, date)):
        return {"$datetime" if isinstance(value, datetime) else "$date": value.isoformat()}
    if isinstance(value, Decimal):
        return {"$decimal": str(value)}
    if isinstance(value, (bytes, memoryview)):
        return {"$bytes_base64": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, dict):
        return {str(key): normalized(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [normalized(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported private snapshot type: {type(value).__name__}")


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def write_private(directory: Path, name: str, value) -> Path:
    require(bool(re.fullmatch(r"[a-z][a-z0-9-]{1,60}", name)), "Invalid evidence name")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{name}.private.json"
    # Every phase gets a new name. Failed attempts cannot overwrite prior evidence.
    with target.open("xb") as output:
        output.write(canonical(value) + b"\n")
    return target


def public_snapshot(snapshot: dict) -> dict:
    state = snapshot["state"]
    tables = state["tables"]
    titles = tables["receivables"]
    payments = tables["payments"]
    return {
        "observed_at_utc": snapshot["observed_at_utc"],
        "state_sha256": digest(state),
        "tables": {
            name: {"rows": len(rows), "sha256": digest(rows)}
            for name, rows in sorted(tables.items())
        },
        "sequence_count": len(state["sequences"]),
        "sequences_sha256": digest(state["sequences"]),
        "receivables": [
            {key: row[key] for key in ("id", "external_receivable_id", "amount_cents", "status")}
            for row in titles
        ],
        "amount_cents": sum(row["amount_cents"] for row in titles),
        "open_cents": sum(row["amount_cents"] for row in titles if row["status"] == "open"),
        "payments": [
            {key: row[key] for key in ("id", "receivable_id", "amount_cents")} for row in payments
        ],
        "payment_cents": sum(row["amount_cents"] for row in payments),
        "reminders": [
            {
                key: row[key]
                for key in ("id", "receivable_id", "status", "lease_token", "attempts_count")
            }
            for row in tables["reminders"]
        ],
        "attempts": [
            {key: row[key] for key in ("id", "reminder_id", "number", "outcome")}
            for row in tables["attempts"]
        ],
        "delivery_ids": [row["id"] for row in tables["deliveries"]],
        "provider_result_attempt_ids": [row["attempt_id"] for row in tables["provider_results"]],
        "private_only": "Complete rows, session/password hashes, payment idempotency keys, CSV bytes and payloads are not published. The UI can show the synthetic reminder key.",
    }


def verify_backup(path: Path, manifest: dict, target: Contract) -> None:
    require(target.role == "dst", "Restore target must be the destination")
    source = Contract(target.run_id, "src")
    require(manifest.get("run_id") == target.run_id, "Backup belongs to another run")
    require(manifest.get("source_database") == source.database, "Backup database mismatch")
    require(manifest.get("source_project") == source.project, "Backup project mismatch")
    expected = manifest.get("dump_sha256", "")
    require(bool(re.fullmatch(r"[a-f0-9]{64}", expected)), "Invalid backup hash manifest")
    require(path.is_file(), "Backup file is absent")
    require(hashlib.sha256(path.read_bytes()).hexdigest() == expected, "Backup checksum mismatch")
