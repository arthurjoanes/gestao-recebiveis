"""Verify real CLI exit codes without a Docker daemon or PostgreSQL."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "tests"))
from restore_support import Contract  # noqa: E402


class BackupCLI(unittest.TestCase):
    def invoke(self, *, corrupted=False, wrong_run=False):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = Contract("a" * 32, "src")
            original = b"PGDMP\x00binary\xff"
            backup = folder / "sample.dump"
            backup.write_bytes(original if not corrupted else b"PGDMP\x00changed\xff")
            manifest = folder / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "run_id": source.run_id,
                        "source_project": source.project,
                        "source_database": source.database,
                        "dump_sha256": hashlib.sha256(original).hexdigest(),
                    }
                )
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/verify_restore_backup.py"),
                    "--backup",
                    str(backup),
                    "--manifest",
                    str(manifest),
                    "--run-id",
                    "b" * 32 if wrong_run else source.run_id,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(
                backup.read_bytes(), original if not corrupted else b"PGDMP\x00changed\xff"
            )
            return result.returncode, json.loads(result.stdout)

    def test_valid_baseline_exits_zero_without_database_access(self):
        code, result = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "validated")
        self.assertFalse(result["database_accessed"])

    def test_corrupted_copy_exits_two_without_database_access(self):
        code, result = self.invoke(corrupted=True)
        self.assertEqual(code, 2)
        self.assertEqual(result["reason"], "Backup checksum mismatch")
        self.assertFalse(result["database_accessed"])

    def test_wrong_run_exits_two_even_with_valid_bytes(self):
        code, result = self.invoke(wrong_run=True)
        self.assertEqual(code, 2)
        self.assertEqual(result["reason"], "Backup belongs to another run")


if __name__ == "__main__":
    unittest.main()
