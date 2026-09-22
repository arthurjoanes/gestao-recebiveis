"""Host-only guard tests: no Docker daemon and no application database imports."""

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend" / "tests"))
from prove_restore import Runner, check_owned, compare_states  # noqa: E402
from restore_support import (  # noqa: E402
    MODE,
    Contract,
    ProofRejected,
    canonical,
    normalized,
    public_snapshot,
    verify_backup,
    write_private,
)


class RestoreGuards(unittest.TestCase):
    def setUp(self):
        self.source = Contract("a" * 32, "src")
        self.target = Contract("a" * 32, "dst")
        self.env = {
            "CF_RESTORE_MODE": MODE,
            "CF_RESTORE_RUN_ID": self.target.run_id,
            "CF_RESTORE_ROLE": "dst",
            "CF_RESTORE_PROJECT": self.target.project,
            "DEMO_MODE": "true",
            "DATABASE_URL": f"postgresql+psycopg://gestao_app:private@db:5432/{self.target.database}",
        }

    def test_exact_contract_passes_and_mode_run_role_project_demo_each_reject(self):
        self.target.validate_environment(self.env)
        for key in (
            "CF_RESTORE_MODE",
            "CF_RESTORE_RUN_ID",
            "CF_RESTORE_ROLE",
            "CF_RESTORE_PROJECT",
            "DEMO_MODE",
        ):
            with self.subTest(key=key), self.assertRaises(ProofRejected):
                self.target.validate_environment({**self.env, key: "wrong"})

    def test_production_url_and_deceptive_test_suffix_reject(self):
        for url in (
            "postgresql+psycopg://gestao_app:private@db:5432/gestao_recebiveis",
            self.env["DATABASE_URL"] + "_test",
            self.env["DATABASE_URL"] + "?options=x",
            self.env["DATABASE_URL"].replace("@db:", "@localhost:"),
            self.env["DATABASE_URL"].replace("gestao_app:", "gestao_owner:"),
        ):
            with self.subTest(url=url), self.assertRaises(ProofRejected):
                self.target.validate_url(url, "gestao_app")

    def test_bad_ids_cannot_create_arbitrary_namespaces(self):
        for run in ("../foo", "A" * 32, "a" * 31, "a" * 33):
            with self.subTest(run=run), self.assertRaises(ProofRejected):
                Contract(run, "dst")
        with self.assertRaises(ProofRejected):
            Contract("a" * 32, "production")

    def test_guard_runs_before_application_imports(self):
        spec = importlib.util.spec_from_file_location(
            "restore_probe_test", ROOT / "backend/tests/restore_probe.py"
        )
        probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(probe)
        before = set(sys.modules)
        with patch.dict("os.environ", {}, clear=True), self.assertRaises(ProofRejected):
            probe.contract_from_environment()
        self.assertFalse(
            any(name.startswith("gestao_recebiveis") for name in set(sys.modules) - before)
        )

    def test_corruption_prevents_any_destination_phase(self):
        with tempfile.TemporaryDirectory() as directory:
            dump = Path(directory) / "source.dump"
            dump.write_bytes(b"PGDMP\x00binary\xff")
            manifest = {
                "run_id": self.target.run_id,
                "source_database": self.source.database,
                "source_project": self.source.project,
                "dump_sha256": hashlib.sha256(dump.read_bytes()).hexdigest(),
            }
            verify_backup(dump, manifest, self.target)
            dump.write_bytes(b"PGDMP\x00changed\xff")
            runner = object.__new__(Runner)
            runner.contracts = {"dst": self.target}
            with (
                patch.object(runner, "phase") as phase,
                self.assertRaisesRegex(ProofRejected, "checksum"),
            ):
                runner.restore(dump, manifest)
            phase.assert_not_called()

    def test_valid_bytes_wrong_run_database_or_project_reject(self):
        with tempfile.TemporaryDirectory() as directory:
            dump = Path(directory) / "source.dump"
            dump.write_bytes(b"PGDMP")
            manifest = {
                "run_id": self.target.run_id,
                "source_database": self.source.database,
                "source_project": self.source.project,
                "dump_sha256": hashlib.sha256(b"PGDMP").hexdigest(),
            }
            for key in ("run_id", "source_database", "source_project", "dump_sha256"):
                with self.subTest(key=key), self.assertRaises(ProofRejected):
                    verify_backup(dump, {**manifest, key: "wrong"}, self.target)

    def test_occupied_destination_stops_before_copy_or_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            dump = Path(directory) / "source.dump"
            dump.write_bytes(b"PGDMP")
            manifest = {
                "run_id": self.target.run_id,
                "source_database": self.source.database,
                "source_project": self.source.project,
                "dump_sha256": hashlib.sha256(b"PGDMP").hexdigest(),
            }
            runner = object.__new__(Runner)
            runner.contracts = {"dst": self.target}
            with (
                patch.object(runner, "phase", side_effect=ProofRejected("occupied")),
                patch.object(runner, "db_id") as identify,
                patch.object(runner, "command") as command,
                self.assertRaisesRegex(ProofRejected, "occupied"),
            ):
                runner.restore(dump, manifest)
            identify.assert_not_called()
            command.assert_not_called()

    def test_cleanup_requires_all_owner_labels_not_only_project(self):
        labels = {**self.target.labels, "com.docker.compose.project": self.target.project}
        for kind in ("containers", "volumes", "networks"):
            item = {"Config": {"Labels": labels}} if kind == "containers" else {"Labels": labels}
            check_owned([item], self.target, kind)
            for key in labels:
                changed = {**labels, key: "foreign"}
                item = (
                    {"Config": {"Labels": changed}} if kind == "containers" else {"Labels": changed}
                )
                with self.subTest(kind=kind, key=key), self.assertRaises(ProofRejected):
                    check_owned([item], self.target, kind)

    def test_private_records_cannot_overwrite_or_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            path = write_private(output, "first", {"secret": "original"})
            with self.assertRaises(FileExistsError):
                write_private(output, "first", {"secret": "changed"})
            with self.assertRaises(ProofRejected):
                write_private(output, "../escape", {})
            self.assertEqual(json.loads(path.read_bytes()), {"secret": "original"})

    def test_exact_comparison_detects_sequence_and_private_row_changes(self):
        baseline = {
            "state": {
                "tables": {"sessions": [{"token_hash": "original"}]},
                "sequences": {"payment_id_seq": {"last_value": 1, "is_called": True}},
            }
        }
        compare_states(baseline, baseline, "changed")
        for section in ("tables", "sequences"):
            modified = json.loads(json.dumps(baseline))
            modified["state"][section] = {}
            with self.subTest(section=section), self.assertRaises(ProofRejected):
                compare_states(baseline, modified, "changed")

    def test_binary_decimal_datetime_serialization_preserves_values(self):
        value = normalized(
            {
                "bytes": b"\x00\xff",
                "amount": Decimal("50.00"),
                "when": datetime(2026, 8, 17, tzinfo=UTC),
            }
        )
        self.assertEqual(value["bytes"], {"$bytes_base64": "AP8="})
        self.assertEqual(value["amount"], {"$decimal": "50.00"})
        self.assertEqual(json.loads(canonical(value)), value)

    def test_public_snapshot_omits_raw_secrets(self):
        tables = {
            name: []
            for name in (
                "receivables",
                "payments",
                "reminders",
                "attempts",
                "deliveries",
                "provider_results",
            )
        }
        tables["sessions"] = [{"token_hash": "DO_NOT_PUBLISH", "csrf_token": "ALSO_PRIVATE"}]
        result = public_snapshot(
            {"state": {"tables": tables, "sequences": {}}, "observed_at_utc": "now"}
        )
        rendered = canonical(result)
        self.assertNotIn(b"DO_NOT_PUBLISH", rendered)
        self.assertNotIn(b"ALSO_PRIVATE", rendered)
        self.assertEqual(result["tables"]["sessions"]["rows"], 1)

    def test_cleanup_failure_cannot_produce_passed(self):
        runner = object.__new__(Runner)
        runner.record = {}
        runner.run_id = "a" * 32
        with (
            patch.object(runner, "freeze_and_build"),
            patch.object(runner, "experiment"),
            patch.object(runner, "cleanup", side_effect=ProofRejected("own resource remains")),
            patch.object(runner, "redact", side_effect=lambda value: value),
            patch.object(runner, "publish"),
            patch.object(runner, "release_lock"),
        ):
            self.assertEqual(runner.execute(), 1)
        self.assertEqual(runner.record["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
