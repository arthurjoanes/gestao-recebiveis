"""Host-only guard tests: no Docker daemon and no application database imports."""

import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import call, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend" / "tests"))
from prove_restore import Runner, check_owned, compare_states, main  # noqa: E402
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
        labels = {
            **self.target.labels,
            "com.docker.compose.project": self.target.project,
        }
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

    def host_runner(self, *, allow_other_projects=False):
        runner = object.__new__(Runner)
        runner.root = ROOT
        runner.allow_other_projects = allow_other_projects
        runner.record = {}
        runner.contracts = {"src": self.source, "dst": self.target}
        return runner

    def test_busy_host_requires_opt_in_before_source_freeze(self):
        runner = self.host_runner()
        with (
            patch.object(
                runner,
                "command",
                return_value="PRIVATE-CONTAINER-ONE\nPRIVATE-CONTAINER-TWO\n",
            ) as command,
            patch("prove_restore.identities") as freeze,
            patch.object(runner, "fresh") as fresh,
            self.assertRaisesRegex(ProofRejected, "quiet window"),
        ):
            runner.freeze_and_build()
        command.assert_called_once_with(["docker", "ps", "-q"])
        freeze.assert_not_called()
        fresh.assert_not_called()
        self.assertFalse(runner.record["host"]["allow_other_projects"])
        self.assertEqual(runner.record["host"]["active_container_count_at_start"], 2)
        self.assertTrue(runner.record["host"]["shared_host_at_start"])
        self.assertNotIn(b"PRIVATE-CONTAINER", canonical(runner.record))

    def test_busy_host_opt_in_keeps_both_fresh_namespace_checks_before_build(self):
        runner = self.host_runner(allow_other_projects=True)
        # Stop at the mocked first build after proving that both real fresh()
        # checks ran. No Docker daemon, copied sources or private setup is needed.
        with (
            patch.object(
                runner,
                "command",
                side_effect=["PRIVATE-CONTAINER\n", ProofRejected("mock build stop")],
            ) as command,
            patch("prove_restore.identities", return_value={}),
            patch("prove_restore.subprocess.check_output", return_value="a" * 40),
            patch.object(
                runner,
                "inventory",
                return_value={"containers": [], "volumes": [], "networks": []},
            ) as inventory,
            self.assertRaisesRegex(ProofRejected, "mock build stop"),
        ):
            runner.run_id = self.source.run_id
            runner.source = ROOT
            runner.freeze_and_build()
        self.assertEqual(inventory.call_args_list, [call(self.source), call(self.target)])
        self.assertEqual(command.call_args_list[0], call(["docker", "ps", "-q"]))
        self.assertEqual(command.call_args_list[1].args[0][:2], ["docker", "build"])
        self.assertEqual(runner.record["status"], "BUILDING")
        self.assertTrue(runner.record["host"]["allow_other_projects"])
        self.assertEqual(runner.record["host"]["active_container_count_at_start"], 1)
        self.assertIn("competing workloads", runner.record["host"]["timing_caveat"])
        self.assertNotIn(b"PRIVATE-CONTAINER", canonical(runner.record))

    def test_busy_host_opt_in_still_refuses_generated_namespace_collision(self):
        runner = self.host_runner(allow_other_projects=True)
        with (
            patch.object(runner, "command", return_value="PRIVATE-CONTAINER\n") as command,
            patch("prove_restore.identities", return_value={}),
            patch("prove_restore.subprocess.check_output", return_value="a" * 40),
            patch.object(
                runner,
                "inventory",
                return_value={
                    "containers": ["owned-existing"],
                    "volumes": [],
                    "networks": [],
                },
            ) as inventory,
            self.assertRaisesRegex(ProofRejected, "Generated project unexpectedly already exists"),
        ):
            runner.freeze_and_build()
        inventory.assert_called_once_with(self.source)
        command.assert_called_once_with(["docker", "ps", "-q"])
        self.assertNotIn("status", runner.record)

    def test_plan_is_read_only_and_reports_shared_host_opt_in(self):
        for enabled in (False, True):
            argv = ["prove_restore.py", "plan"] + (["--allow-other-projects"] if enabled else [])
            with (
                self.subTest(enabled=enabled),
                patch.object(sys, "argv", argv),
                patch("sys.stdout", new_callable=io.StringIO) as output,
                patch("prove_restore.Runner") as runner,
            ):
                self.assertEqual(main(), 0)
                plan = json.loads(output.getvalue())
                self.assertEqual(plan["allow_other_projects"], enabled)
                self.assertEqual(plan["quiet_window_required"], not enabled)
                self.assertIn("Shared host workloads", plan["timing_caveat"])
                runner.assert_not_called()

    def test_execute_forwards_shared_host_opt_in_without_bypassing_runner(self):
        with (
            patch.object(sys, "argv", ["prove_restore.py", "execute", "--allow-other-projects"]),
            patch("prove_restore.Runner") as runner,
        ):
            runner.return_value.execute.return_value = 0
            self.assertEqual(main(), 0)
        runner.assert_called_once_with(ROOT, 1200, allow_other_projects=True)
        runner.return_value.execute.assert_called_once_with()

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

    def test_public_snapshot_uses_residual_and_keeps_canceled_nominal(self):
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
        tables["receivables"] = [
            {
                "id": 1,
                "external_receivable_id": "PARTIAL",
                "amount_cents": 7500,
                "status": "open",
            },
            {
                "id": 2,
                "external_receivable_id": "CANCELED",
                "amount_cents": 1000,
                "status": "canceled",
            },
        ]
        tables["payments"] = [
            {"id": 1, "receivable_id": 1, "amount_cents": 2000},
            {"id": 2, "receivable_id": 1, "amount_cents": 500},
        ]
        result = public_snapshot(
            {"state": {"tables": tables, "sequences": {}}, "observed_at_utc": "now"}
        )
        self.assertEqual(result["open_cents"], 5000)
        self.assertEqual(result["receivables"][0]["paid_cents"], 2500)
        self.assertEqual(result["receivables"][1]["remaining_cents"], 1000)

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
