"""Read-only CLI for the restore proof's existing backup guard.

Exit 0 means the bytes/run/source match the manifest. Exit 2 means refusal.
This command does not connect to Docker or PostgreSQL and does not restore data.
The expected SHA-256 manifest is local evidence, not a signature/authenticity claim.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "tests"))
from restore_support import Contract, ProofRejected, require, verify_backup  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    try:
        target = Contract(args.run_id, "dst")
        manifest = json.loads(args.manifest.read_bytes())
        require(isinstance(manifest, dict), "Backup manifest must be an object")
        verify_backup(args.backup, manifest, target)
    except (ProofRejected, OSError, ValueError) as error:
        reason = str(error) if isinstance(error, ProofRejected) else "Backup or manifest unreadable"
        print(json.dumps({"status": "rejected", "reason": reason, "database_accessed": False}))
        return 2
    print(
        json.dumps(
            {
                "status": "validated",
                "run_id": target.run_id,
                "dump_sha256": manifest["dump_sha256"],
                "database_accessed": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
