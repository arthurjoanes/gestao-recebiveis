"""Isolated backup/restore proof. `plan` is read-only; `execute` creates fresh resources.

The existing restart proof is deliberately independent. Private dumps and complete
database snapshots never enter docs/evidence. All Docker mutations use generated
projects and verified ownership labels; no global prune or shared stack operation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "tests"))
from restore_support import (  # noqa: E402
    FIXTURE,
    MODE,
    Contract,
    ProofRejected,
    canonical,
    digest,
    require,
    verify_backup,
)


def now() -> str:
    return datetime.now(UTC).isoformat()


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical(value) + b"\n")


def protect(directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=False)
    if os.name == "nt":
        identity = subprocess.check_output(["whoami", "/user", "/fo", "csv", "/nh"], text=True)
        sid = next(csv.reader(io.StringIO(identity)))[1]
        require(sid.startswith("S-1-"), "Could not resolve current Windows SID")
        subprocess.run(
            [
                "icacls",
                str(directory),
                "/inheritance:r",
                "/grant:r",
                f"*{sid}:(OI)(CI)F",
                "*S-1-5-18:(OI)(CI)F",
            ],
            check=True,
            capture_output=True,
        )
        inspect_acl = (
            "$a=Get-Acl -LiteralPath $env:GR_RESTORE_ACL_DIRECTORY; "
            "$r=@($a.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier]) | "
            "ForEach-Object { @{sid=$_.IdentityReference.Value; inherited=$_.IsInherited; "
            "type=$_.AccessControlType.ToString(); rights=[int]$_.FileSystemRights} }); "
            "@{protected=$a.AreAccessRulesProtected; rules=$r} | ConvertTo-Json -Depth 5 -Compress"
        )
        acl = json.loads(
            subprocess.check_output(
                [
                    shutil.which("pwsh") or "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    inspect_acl,
                ],
                env={**os.environ, "GR_RESTORE_ACL_DIRECTORY": str(directory)},
                text=True,
            )
        )
        require(
            acl["protected"] is True
            and {r["sid"] for r in acl["rules"]} == {sid, "S-1-5-18"}
            and all(
                not r["inherited"] and r["type"] == "Allow" and r["rights"] & 2032127 == 2032127
                for r in acl["rules"]
            ),
            "Private evidence ACL verification failed",
        )
        return {
            "method": "Windows ACL",
            "inheritance": False,
            "allowed": ["current user", "SYSTEM"],
            "applied_before_secrets": True,
            "verified_from_final_dacl": True,
        }
    directory.chmod(0o700)
    return {"method": "POSIX mode", "directory_mode": "0700", "applied_before_secrets": True}


def identities(root: Path) -> dict:
    listing = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root
        )
        .decode()
        .split("\0")
    )
    selected = {}
    for name in sorted(set(listing)):
        parts = Path(name).parts
        if not parts or not name:
            continue
        if parts[0] not in {"backend", "frontend", "database", "data", "scripts"} and name not in {
            "compose.restore-proof.yaml",
            ".dockerignore",
        }:
            continue
        if any(
            part in {"node_modules", ".next", "__pycache__", ".venv", "artifacts"}
            or part.startswith(".env")
            for part in parts
        ):
            continue
        path = root / name
        require(path.is_file() and not path.is_symlink(), "Source is missing or a symlink")
        data = path.read_bytes()
        selected[Path(name).as_posix()] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "lf_sha256": hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest(),
            "bytes": len(data),
        }
    require(
        "data/cenarios_cobranca.csv" in selected or any(n.startswith("data/") for n in selected),
        "Source inventory must include fixture data",
    )
    return selected


def check_owned(objects: list[dict], contract: Contract, kind: str) -> None:
    for item in objects:
        labels = (
            item.get("Config", {}).get("Labels", {})
            if kind == "containers"
            else item.get("Labels", {})
        )
        labels = labels or {}
        require(
            all(labels.get(key) == value for key, value in contract.labels.items()),
            f"Refusing foreign {kind} ownership",
        )
        require(
            labels.get("com.docker.compose.project") == contract.project,
            f"Refusing foreign {kind} project",
        )


def compare_states(first: dict, second: dict, reason: str) -> None:
    require(first["state"] == second["state"], reason)


class Runner:
    def __init__(self, root: Path, deadline_seconds: int = 1200):
        require(300 <= deadline_seconds <= 1800, "Deadline must be between 300 and 1800 seconds")
        self.root = root
        self.run_id = uuid.uuid4().hex
        parent = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share")))
        parent = parent / "gestao-recebiveis-restore"
        parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = parent / "operation.lock"
        self.lock = self.lock_path.open("xb")
        self.lock.write(self.run_id.encode())
        self.lock.flush()
        self.private = parent / self.run_id
        self.started = time.monotonic()
        self.deadline = self.started + deadline_seconds
        self.cleanup_mode = False
        self.calls = []
        self.secret_values = []
        self.contracts = {role: Contract(self.run_id, role) for role in ("src", "dst")}
        self.env_files = {}
        self.images = {}
        self.preexisting = []
        self.record = {
            "schema": 1,
            "run_id": self.run_id,
            "status": "PREPARING",
            "started_at": now(),
            "fixture": FIXTURE,
            "checks": {},
            "deadline_seconds": deadline_seconds,
            "deadline_scope": "Operational budget includes a 75-second cleanup reserve. Cleanup may extend up to 60 seconds from its start if the operational deadline is exhausted; this is not a hard total-runtime guarantee.",
            "limits": [
                "Synthetic fixture on one host, not a production recovery SLA",
                "Fake-provider delivery and result ledger live in the same restored database",
                "SHA-256 detects accidental corruption; it is not backup authentication",
                "Source is quiescent at cut; this does not test concurrent pg_dump writers",
                "No external payment, email or provider API is called",
            ],
        }
        try:
            self.record["private_protection"] = protect(self.private)
            self.evidence = self.private / "evidence"
            self.evidence.mkdir()
            self.source = self.private / "source"
            self.source.mkdir()
        except BaseException as error:
            # No credentials exist yet; retain a failed ACL/preflight attempt.
            self.record["status"] = "PREFLIGHT_FAILED"
            self.record["failure"] = {"type": type(error).__name__, "message": str(error)}
            self.record["docker_started"] = False
            self.record["credentials_generated"] = False
            save(
                self.root / "docs" / "evidence" / "restore-proof" / self.run_id / "manifest.json",
                self.record,
            )
            self.release_lock()
            raise

    def release_lock(self):
        self.lock.close()
        if self.lock_path.read_text() == self.run_id:
            self.lock_path.unlink()

    def redact(self, value: str) -> str:
        for secret in self.secret_values:
            value = value.replace(secret, "[private credential]")
        return value.replace(str(self.private), "[private run directory]")

    def command(self, args, *, timeout=120, expected=0, cwd=None):
        remaining = self.deadline - time.monotonic()
        if not self.cleanup_mode:
            remaining -= 75  # reserve bounded cleanup time
        require(remaining > 0, "Global proof deadline exhausted")
        begin = time.monotonic()
        number = len(self.calls) + 1
        try:
            result = subprocess.run(
                args,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=min(timeout, remaining),
            )
        except subprocess.TimeoutExpired as error:
            save(
                self.private / f"command-{number:03d}-timeout.json",
                {"args": args, "timeout": error.timeout},
            )
            self.calls.append(
                {
                    "number": number,
                    "command": self.redact(subprocess.list2cmdline(args)),
                    "status": "timeout",
                    "seconds": time.monotonic() - begin,
                }
            )
            raise ProofRejected("Command timed out; see private command record") from error
        save(
            self.private / f"command-{number:03d}.json",
            {
                "args": args,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
            },
        )
        self.calls.append(
            {
                "number": number,
                "command": self.redact(subprocess.list2cmdline(args)),
                "exit_code": result.returncode,
                "seconds": time.monotonic() - begin,
            }
        )
        require(
            result.returncode == expected,
            f"Command {number} returned {result.returncode}, expected {expected}; private log retained",
        )
        return result.stdout

    def docker_json(self, args):
        return json.loads(self.command(["docker", *args]))

    def inventory(self, contract: Contract) -> dict:
        result = {}
        for kind, cli in (
            ("containers", ["ps", "-aq"]),
            ("volumes", ["volume", "ls", "-q"]),
            ("networks", ["network", "ls", "-q"]),
        ):
            names = self.command(
                ["docker", *cli, "--filter", f"label=com.docker.compose.project={contract.project}"]
            ).split()
            inspect = {
                "containers": ["inspect"],
                "volumes": ["volume", "inspect"],
                "networks": ["network", "inspect"],
            }[kind]
            objects = self.docker_json([*inspect, *names]) if names else []
            check_owned(objects, contract, kind)
            result[kind] = [item.get("Id", item.get("ID", item.get("Name"))) for item in objects]
        return result

    def fresh(self, role):
        inventory = self.inventory(self.contracts[role])
        require(not any(inventory.values()), "Generated project unexpectedly already exists")
        return inventory

    def compose(self, role, args, *, timeout=120, expected=0):
        require(role in self.env_files, "Project environment not initialized")
        return self.command(
            [
                "docker",
                "compose",
                "--env-file",
                str(self.env_files[role]),
                "--file",
                str(self.source / "compose.restore-proof.yaml"),
                "--project-name",
                self.contracts[role].project,
                *args,
            ],
            timeout=timeout,
            expected=expected,
        )

    def phase(self, role, phase, name=None, expected=0):
        args = [
            "run",
            "--rm",
            "--no-deps",
            "-T",
            "probe",
            "python",
            "tests/restore_probe.py",
            phase,
        ]
        if name:
            args += ["--name", name]
        output = self.compose(role, args, expected=expected)
        record = json.loads(output.strip().splitlines()[-1])
        if expected == 0:
            require(
                record.get("role") == role and record.get("phase") == phase,
                "Probe result identity mismatch",
            )
        else:
            require(
                record.get("status") == "rejected", "Negative control failed for another reason"
            )
        key = f"{role}-{name or phase}"
        require(key not in self.record["checks"], "Evidence phase repeated")
        self.record["checks"][key] = record
        print(json.dumps({"run_id": self.run_id, "phase": key, "at": now()}), flush=True)
        return record.get("result", record)

    def db_id(self, role):
        self.inventory(self.contracts[role])
        ids = self.compose(role, ["ps", "-q", "db"]).split()
        require(len(ids) == 1, "Expected one owned database container")
        detail = self.docker_json(["inspect", ids[0]])[0]
        check_owned([detail], self.contracts[role], "containers")
        require(detail["Image"] == self.images["database"]["id"], "Database image changed")
        return ids[0]

    def db_command(self, role, args, timeout=120):
        return self.command(
            ["docker", "exec", "--user", "postgres", self.db_id(role), *args], timeout=timeout
        )

    def private_snapshot(self, name):
        return json.loads((self.evidence / f"{name}.private.json").read_bytes())

    def freeze_and_build(self):
        require(
            not self.command(["docker", "ps", "-q"]).strip(),
            "Active containers detected; run in an agreed quiet window",
        )
        self.record["host"] = {
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "monotonic_clock": vars(time.get_clock_info("monotonic")),
        }
        sources = identities(self.root)
        for name in sources:
            target = self.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.root / name, target)
            require(sha(target) == sources[name]["sha256"], "Source changed while freezing")
        self.record["sources"] = sources
        self.record["source_manifest_sha256"] = digest(sources)
        self.record["git_head_at_freeze"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.root, text=True
        ).strip()
        for role in self.contracts:
            self.fresh(role)
        self.record["status"] = "BUILDING"
        builds = {
            "database": [
                "--file",
                str(self.source / "database" / "Dockerfile"),
                str(self.source / "database"),
            ],
            "backend": ["--file", str(self.source / "backend" / "Dockerfile"), str(self.source)],
            "frontend": [
                "--target",
                "runtime",
                "--build-arg",
                "API_INTERNAL_URL=http://api:8101",
                "--file",
                str(self.source / "frontend" / "Dockerfile"),
                str(self.source / "frontend"),
            ],
        }
        for component, args in builds.items():
            tag = f"pf-gr-restore-{component}:{self.run_id}"
            print(
                json.dumps({"run_id": self.run_id, "phase": f"build-{component}", "at": now()}),
                flush=True,
            )
            self.command(["docker", "build", "--tag", tag, *args], timeout=600)
            image = self.docker_json(["image", "inspect", tag])[0]
            self.images[component] = {
                "id": image["Id"],
                "tag": tag,
                "created": image["Created"],
                "repo_digests": image["RepoDigests"],
            }
        self.record["images"] = self.images
        # Verify actual Python files in the image against the frozen source, not just its tag.
        checks = {
            "/app/" + n.removeprefix("backend/"): value["sha256"]
            for n, value in sources.items()
            if n.startswith("backend/") and n.endswith(".py")
        }
        program = (
            "import hashlib,json; p="
            + repr(checks)
            + "; print(json.dumps({n:hashlib.sha256(open(n,'rb').read()).hexdigest() for n in p}))"
        )
        check_contract = self.contracts["src"]
        labels = {**check_contract.labels, "com.docker.compose.project": check_contract.project}
        label_args = [
            argument for key, value in labels.items() for argument in ("--label", f"{key}={value}")
        ]
        actual = json.loads(
            self.command(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    "none",
                    "--name",
                    check_contract.project + "-image-check",
                    "--memory",
                    "128m",
                    "--cpus",
                    "0.5",
                    *label_args,
                    self.images["backend"]["id"],
                    "python",
                    "-c",
                    program,
                ]
            )
        )
        require(actual == checks, "Image Python sources differ from frozen build inputs")
        self.record["image_python_files_verified"] = len(checks)
        for role, contract in self.contracts.items():
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            values = {
                "GR_RESTORE_PROJECT": contract.project,
                "GR_RESTORE_RUN_ID": self.run_id,
                "GR_RESTORE_ROLE": role,
                "GR_RESTORE_DATABASE": contract.database,
                "GR_RESTORE_PORT": str(port),
                "GR_RESTORE_PRIVATE_EVIDENCE": self.evidence.as_posix(),
                **{
                    f"GR_RESTORE_{key.upper()}_IMAGE": value["id"]
                    for key, value in self.images.items()
                },
            }
            for key in (
                "ADMIN_PASSWORD",
                "OWNER_PASSWORD",
                "APP_PASSWORD",
                "SESSION_SECRET",
                "OPERATOR_PASSWORD",
            ):
                values[f"GR_RESTORE_{key}"] = secrets.token_hex(24)
                self.secret_values.append(values[f"GR_RESTORE_{key}"])
            if role == "dst":
                # The restored synthetic operator is the same account. Session signing secrets differ.
                values["GR_RESTORE_OPERATOR_PASSWORD"] = self.operator_password
            else:
                self.operator_password = values["GR_RESTORE_OPERATOR_PASSWORD"]
            path = self.private / f"{role}.env"
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write("".join(f"{key}={value}\n" for key, value in values.items()))
            self.env_files[role] = path
            self.record.setdefault("projects", {})[role] = {
                "project": contract.project,
                "database": contract.database,
                "loopback_url": f"http://127.0.0.1:{port}",
                "labels": contract.labels,
            }

    def capture(self, role, phase, fixture, cut=None):
        ids = self.compose(role, ["ps", "-q", "frontend"]).split()
        require(len(ids) == 1, "Expected one owned frontend")
        detail = self.docker_json(["inspect", ids[0]])[0]
        check_owned([detail], self.contracts[role], "containers")
        require(detail["Image"] == self.images["frontend"]["id"], "Frontend image changed")
        bindings = detail["NetworkSettings"]["Ports"].get("3101/tcp") or []
        expected_port = str(urlsplit(self.record["projects"][role]["loopback_url"]).port)
        require(
            bindings == [{"HostIp": "127.0.0.1", "HostPort": expected_port}],
            "Frontend loopback publication is absent or broader than the proof contract",
        )
        config = {
            "run_id": self.run_id,
            "phase": phase,
            "origin": self.record["projects"][role]["loopback_url"],
            "email": FIXTURE["operator_email"],
            "password": self.operator_password,
            "fixture": fixture,
            "cut": cut,
            "output": str(self.private / "screenshots"),
            "playwright_module": str(
                self.root / "frontend" / "node_modules" / "@playwright" / "test"
            ),
        }
        config_path = self.private / f"capture-{phase}.json"
        save(config_path, config)
        output = self.command(
            [
                "node",
                str(self.source / "scripts" / "capture_restore_story.cjs"),
                "--config",
                str(config_path),
            ],
            timeout=90,
        )
        record = json.loads(output.strip().splitlines()[-1])
        require(
            record["run_id"] == self.run_id and record["phase"] == phase,
            "Capture identity mismatch",
        )
        self.record.setdefault("captures", []).append(record)

    def restore(self, dump: Path, manifest: dict):
        # File validation precedes any destination command. An existing schema is never overwritten.
        verify_backup(dump, manifest, self.contracts["dst"])
        self.phase("dst", "assert-empty")
        container = self.db_id("dst")
        self.command(["docker", "cp", str(dump), f"{container}:/tmp/restore-input.dump"])
        self.db_command(
            "dst",
            [
                "pg_restore",
                "--username",
                "gestao_restore_admin",
                "--dbname",
                self.contracts["dst"].database,
                "--exit-on-error",
                "--single-transaction",
                "--no-owner",
                "--no-acl",
                "/tmp/restore-input.dump",
            ],
        )

    def experiment(self):
        self.record["status"] = "RUNNING"
        self.compose("src", ["up", "-d", "--wait", "db"])
        self.compose("src", ["run", "--rm", "--no-deps", "-T", "provision"])
        self.compose("src", ["run", "--rm", "--no-deps", "-T", "migrate"])
        self.phase("src", "verify-roles")
        fixture = self.phase("src", "initialize")
        self.compose("src", ["up", "-d", "--wait", "api", "frontend"])
        self.capture("src", "imported", fixture)
        conflict = self.phase("src", "conflict")
        self.capture("src", "conflict", {**fixture, "conflict_batch_id": conflict["batch_id"]})
        self.compose("src", ["stop", "api", "frontend"])
        running = self.compose("src", ["ps", "--status", "running", "--services"]).split()
        require(running == ["db"], "Writers are still running at the backup cut")
        cut = self.phase("src", "cut")
        self.phase("src", "snapshot", "source-cut")
        self.record["cut_recorded_at"] = now()
        backup_started = time.monotonic()
        source_container = self.db_id("src")
        self.db_command(
            "src",
            [
                "pg_dump",
                "--username",
                "gestao_restore_admin",
                "--dbname",
                self.contracts["src"].database,
                "--format=custom",
                "--no-owner",
                "--no-acl",
                "--file",
                "/tmp/restore-cut.dump",
            ],
        )
        dump = self.private / "source-cut.dump"
        self.command(["docker", "cp", f"{source_container}:/tmp/restore-cut.dump", str(dump)])
        require(
            dump.read_bytes().startswith(b"PGDMP"), "Dump is not PostgreSQL custom binary format"
        )
        backup = {
            "run_id": self.run_id,
            "source_project": self.contracts["src"].project,
            "source_database": self.contracts["src"].database,
            "dump_sha256": sha(dump),
            "bytes": dump.stat().st_size,
            "format": "PostgreSQL custom PGDMP",
            "cut_state_sha256": digest(self.private_snapshot("source-cut")["state"]),
            "created_at": now(),
            "published": False,
        }
        save(self.private / "backup-manifest.json", backup)
        self.record["backup"] = backup
        self.record["timings"] = {
            "backup_dump_copy_hash_seconds": time.monotonic() - backup_started
        }
        self.phase("src", "snapshot", "source-after-dump")
        compare_states(
            self.private_snapshot("source-cut"),
            self.private_snapshot("source-after-dump"),
            "Backup operation changed source state",
        )
        corrupt = self.private / "corrupted-control.dump"
        damaged = bytearray(dump.read_bytes())
        damaged[len(damaged) // 2] ^= 1
        corrupt.write_bytes(damaged)
        before_target = self.fresh("dst")
        try:
            self.restore(corrupt, backup)
        except ProofRejected as error:
            require(
                str(error) == "Backup checksum mismatch", "Corruption failed for another reason"
            )
        else:
            raise ProofRejected("Corrupted backup was accepted")
        require(
            self.fresh("dst") == before_target, "Corruption control created destination resources"
        )
        self.record["checks"]["corruption"] = {
            "rejected_before_destination_creation": True,
            "original_sha256": sha(dump),
            "corrupted_sha256": sha(corrupt),
        }
        recovery_started = time.monotonic()
        self.compose("dst", ["up", "-d", "--wait", "db"])
        self.compose("dst", ["run", "--rm", "--no-deps", "-T", "provision"])
        restore_started = time.monotonic()
        self.record["timings"]["destination_setup_seconds"] = restore_started - recovery_started
        self.restore(dump, backup)
        validation_started = time.monotonic()
        self.record["timings"]["restore_guard_copy_pg_restore_seconds"] = (
            validation_started - restore_started
        )
        self.compose("dst", ["run", "--rm", "--no-deps", "-T", "provision"])
        self.phase("dst", "verify-roles")
        self.phase("dst", "snapshot", "restored-before-replay")
        compare_states(
            self.private_snapshot("source-cut"),
            self.private_snapshot("restored-before-replay"),
            "Restored rows, IDs or sequences differ from the backup cut",
        )
        self.record["checks"]["exact_restore"] = {
            "all_public_tables_and_sequences_equal": True,
            "before_login_or_replay": True,
        }
        verify_backup(dump, backup, self.contracts["dst"])
        self.phase("dst", "assert-empty", "occupied-target", expected=2)
        self.phase("dst", "snapshot", "after-occupied-refusal")
        compare_states(
            self.private_snapshot("restored-before-replay"),
            self.private_snapshot("after-occupied-refusal"),
            "Occupied-target refusal changed data",
        )
        # Wrong-mode control must stop before importing the application database engine.
        output = self.compose(
            "dst",
            [
                "run",
                "--rm",
                "--no-deps",
                "-T",
                "-e",
                "CF_RESTORE_MODE=refused",
                "probe",
                "python",
                "tests/restore_probe.py",
                "snapshot",
                "--name",
                "wrong-mode",
            ],
            expected=2,
        )
        require(
            json.loads(output.strip().splitlines()[-1])["reason"] == "Restore mode rejected",
            "Wrong-mode control failed for another reason",
        )
        self.record["checks"]["wrong_mode"] = {"rejected_before_engine_import": True}
        self.phase("dst", "replay")
        self.phase("dst", "reconcile")
        self.record["timings"][
            "ownership_exact_restore_negative_controls_replay_reconciliation_seconds"
        ] = time.monotonic() - validation_started
        self.record["timings"]["destination_setup_through_reconciliation_seconds"] = (
            time.monotonic() - recovery_started
        )
        self.phase("src", "snapshot", "source-final")
        compare_states(
            self.private_snapshot("source-cut"),
            self.private_snapshot("source-final"),
            "Source state changed during destination recovery",
        )
        require(sha(dump) == backup["dump_sha256"], "Original dump changed")
        self.record["checks"]["source_unchanged"] = {
            "all_rows_and_sequences_equal": True,
            "dump_bytes_unchanged": True,
        }
        self.compose("dst", ["up", "-d", "--wait", "api", "frontend"])
        self.capture("dst", "recovered", fixture, cut)
        self.record["capture_session_limit"] = (
            "Source logins precede cut; destination login follows exact restore/replay/reconciliation comparisons. Capture sessions are legitimate later writes."
        )

    def cleanup(self):
        self.cleanup_mode = True
        self.deadline = max(self.deadline, time.monotonic() + 60)
        results = {}
        for role, contract in self.contracts.items():
            before = self.inventory(contract)  # ownership checked before any destructive command
            if role in self.env_files and any(before.values()):
                self.compose(
                    role, ["down", "--volumes", "--remove-orphans", "--timeout", "15"], timeout=35
                )
            elif before["containers"]:
                # Only the labeled image-source check can exist before env files are written.
                require(
                    not before["volumes"] and not before["networks"],
                    "Unexpected early project resources require inspection",
                )
                for container in before["containers"]:
                    detail = self.docker_json(["inspect", container])[0]
                    check_owned([detail], contract, "containers")
                    require(
                        detail["Name"].lstrip("/") == contract.project + "-image-check",
                        "Unexpected early container requires inspection",
                    )
                    self.command(["docker", "rm", "--force", container], timeout=15)
            after = self.inventory(contract)
            results[role] = {"before": before, "after": after}
            require(not any(after.values()), "Own project resources remain after cleanup")
        self.record["cleanup"] = results

    def publish(self):
        current = identities(self.root)
        previous = self.record.get("sources", {})
        self.record["source_comparison"] = {
            "same": previous == current,
            "changed_paths": sorted(
                n for n in previous.keys() | current.keys() if previous.get(n) != current.get(n)
            ),
            "note": "The experiment uses the frozen sources above; later working-tree changes are not retroactively tested.",
        }
        self.record["finished_at"] = now()
        self.record["duration_seconds"] = time.monotonic() - self.started
        self.record["commands"] = self.calls
        self.record["private_artifacts"] = [
            {"name": p.name, "sha256": sha(p), "bytes": p.stat().st_size, "published": False}
            for p in sorted(self.evidence.glob("*.json"))
        ]
        base = self.root / "docs" / "evidence" / "restore-proof" / self.run_id
        screenshots = self.root / "docs" / "screenshots" / "restore-proof" / self.run_id
        self.record["screenshots"] = []
        for path in sorted((self.private / "screenshots").glob("*.png")):
            screenshots.mkdir(parents=True, exist_ok=True)
            target = screenshots / path.name
            require(not target.exists(), "Screenshot destination already exists")
            shutil.copyfile(path, target)
            self.record["screenshots"].append(
                {
                    "path": target.relative_to(self.root).as_posix(),
                    "sha256": sha(target),
                    "bytes": target.stat().st_size,
                }
            )
        public = canonical(self.record)
        require(
            not any(value.encode() in public for value in self.secret_values),
            "Known credential detected in public evidence",
        )
        require(
            str(self.private).encode() not in public,
            "Private absolute path detected in public evidence",
        )
        save(base / "manifest.json", self.record)
        save(self.private / "result.json", self.record)
        print(
            json.dumps(
                {
                    "run_id": self.run_id,
                    "status": self.record["status"],
                    "manifest": str(base / "manifest.json"),
                }
            ),
            flush=True,
        )

    def execute(self):
        success = False
        try:
            self.freeze_and_build()
            self.experiment()
            success = True
        except BaseException as error:
            self.record["failure"] = {
                "type": type(error).__name__,
                "message": self.redact(str(error)),
            }
            print(
                json.dumps({"run_id": self.run_id, "failure": self.record["failure"]}), flush=True
            )
        finally:
            try:
                self.cleanup()
            except BaseException as error:
                success = False
                self.record["cleanup_failure"] = {
                    "type": type(error).__name__,
                    "message": self.redact(str(error)),
                }
            self.record["status"] = "PASSED" if success else "FAILED"
            try:
                self.publish()
            finally:
                self.release_lock()
        return 0 if success else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "execute"))
    parser.add_argument("--deadline-seconds", type=int, default=1200)
    args = parser.parse_args()
    if args.action == "plan":
        print(
            json.dumps(
                {
                    "fixture": FIXTURE,
                    "mode": MODE,
                    "services": "Two private PostgreSQL volumes; API/frontend started only for real captures; no worker",
                    "runtime_memory_limit_mib": 896,
                    "peak_runtime_memory_limit_mib": 1280,
                    "memory_limit_scope": "Sum of active service/probe container limits; host browser and sequential builds are additional",
                    "builds": "Three sequential builds from frozen source; build resource use is reported separately",
                    "deadline_seconds": args.deadline_seconds,
                    "private_dump": True,
                    "cleanup_budget": "75 seconds reserved; emergency cleanup can extend up to 60 seconds beyond operational deadline",
                    "public_evidence": "docs/evidence/restore-proof/<run_id>/manifest.json",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    return Runner(ROOT, args.deadline_seconds).execute()


if __name__ == "__main__":
    raise SystemExit(main())
