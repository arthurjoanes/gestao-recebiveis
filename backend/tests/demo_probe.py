"Executa o roteiro pela API após reset."

import json
import os
from pathlib import Path
from time import monotonic, sleep
from typing import Any

import httpx

from gestao_recebiveis.config import get_settings


def wait_for_title(client: httpx.Client, title_id: int, stage: int, status: str) -> dict[str, Any]:
    deadline = monotonic() + 60
    while monotonic() < deadline:
        response = client.get(f"/receivables/{title_id}")
        response.raise_for_status()
        title: dict[str, Any] = response.json()
        if any(job["stage"] == stage and job["status"] == status for job in title["reminders"]):
            return title
        sleep(0.25)
    raise AssertionError(f"Lembrete stage={stage}/status={status} não observado em 60s.")


def main() -> None:
    if os.environ.get("CF_PROOF_MODE") != "isolated" or not get_settings().database_url.endswith(
        "/gestao_recebiveis_proof_test"
    ):
        raise SystemExit("Roteiro restrito à aplicação descartável de compose.proof.yaml.")
    with httpx.Client(
        base_url="http://frontend:3101/api/v1",
        headers={"Origin": get_settings().frontend_origin},
        timeout=15,
    ) as client:
        login = client.post(
            "/auth/login", json={"email": "operador@example.com", "password": "Recebiveis!2026"}
        )
        login.raise_for_status()
        client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        state = client.get("/demo").json()
        assert state["enabled"] and state["business_date"] == "2026-08-17", (
            "Restaure a demonstração antes do roteiro."
        )
        client.post("/demo/worker", json={"enabled": False}).raise_for_status()
        assert client.get("/receivables").json()["total"] == 240, (
            "Restaure a carteira antes do roteiro."
        )

        def import_file(name: str) -> dict[str, Any]:
            response = client.post(
                "/imports",
                files={"file": (name, Path("/data/samples", name).read_bytes(), "text/csv")},
            )
            response.raise_for_status()
            return response.json()

        first = import_file("valid.csv")
        assert first["report"]["new_count"] == 3
        assert first["report"]["total_cents"] == "200000"
        assert client.post(f"/imports/{first['id']}/confirm").json()["status"] == "confirmed"
        assert client.get("/receivables").json()["total"] == 243
        after_import = client.get("/overview").json()
        for filename in ("repeated.csv", "reordered.csv"):
            batch = import_file(filename)
            assert batch["report"]["existing_count"] == 3
            assert client.post(f"/imports/{batch['id']}/confirm").json()["report"]["new_count"] == 0
            assert client.get("/overview").json() == after_import

        title_one = client.get("/receivables", params={"q": "DEMO-001"}).json()["items"][0]
        client.post(
            "/demo/scenario", json={"receivable_id": title_one["id"], "scenario": "transient"}
        ).raise_for_status()
        client.post("/demo/worker", json={"enabled": True}).raise_for_status()
        sent = wait_for_title(client, title_one["id"], 3, "sent")
        sent_job = next(job for job in sent["reminders"] if job["stage"] == 3)
        assert [attempt["outcome"] for attempt in sent_job["attempts"]] == ["transient", "success"]
        assert sent_job["delivery"] is not None
        client.post("/demo/worker", json={"enabled": False}).raise_for_status()
        client.post(
            "/demo/clock", json={"business_now": "2026-08-20T10:00:00-03:00"}
        ).raise_for_status()
        title_three = client.get("/receivables", params={"q": "DEMO-003"}).json()["items"][0]
        wait_for_title(client, title_three["id"], 0, "pending")
        payload = {
            "idempotency_key": "demo-probe-payment-003",
            "note": "Pagamento integral do roteiro reproduzível",
        }
        payment = client.post(f"/receivables/{title_three['id']}/payments", json=payload)
        payment.raise_for_status()
        repeated = client.post(f"/receivables/{title_three['id']}/payments", json=payload)
        assert repeated.json()["id"] == payment.json()["id"]
        paid = client.get(f"/receivables/{title_three['id']}").json()
        assert paid["status"] == "paid"
        assert any(job["stage"] == 0 and job["status"] == "canceled" for job in paid["reminders"])
        assert any(event["type"] == "payment_recorded" for event in paid["events"])
        before_conflict = client.get("/overview").json()
        conflicting = import_file("conflicting.csv")
        assert conflicting["report"]["errors"]
        assert client.post(f"/imports/{conflicting['id']}/confirm").json()["status"] == "rejected"
        assert client.get("/overview").json() == before_conflict
        assert client.get("/receivables", params={"q": "DEMO-004"}).json()["total"] == 0
        print(
            json.dumps(
                {
                    "result": "passed",
                    "titles": 243,
                    "retry_attempts": 2,
                    "payment_cents": payment.json()["amount_cents"],
                    "pending_canceled": True,
                    "conflict_preserved_totals": True,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
