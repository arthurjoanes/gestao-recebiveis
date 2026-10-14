"""V2 limits history materialization; v1 remains a compatibility contract."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_api import login
from test_reports import customer, receivable

from gestao_recebiveis.receivables import pay


def test_v2_summaries_and_complete_paginated_history(client: TestClient, db: Session) -> None:
    owner = customer(db)
    title = receivable(db, owner, "MANY-PARTIALS", 1, 1000)
    for index in range(205):
        pay(db, title.id, f"v2-partial-{index:04d}", "Parcela sintética", 1, "1")
    db.commit()
    login(client, "leitor")
    for path in ["/receivables", "/reports/aging", f"/customers/{owner.id}/statement"]:
        response = client.get("/api/v2" + path)
        assert response.status_code == 200, response.text
        data = response.json()
        item = (data["titles"] if "titles" in data else data)["items"][0]
        assert "payments" not in item
        assert (item["paid_cents"], item["remaining_cents"]) == ("205", "795")
    seen = []
    event_ids = []
    for page in range(1, 4):
        response = client.get(
            f"/api/v2/receivables/{title.id}",
            params={"page_size": 100, "payment_page": page, "event_page": page},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["paid_cents"] == "205"
        assert data["history"]["payments"]["total"] == 205
        assert len(data["payments"]) <= 100 and len(data["events"]) <= 100
        seen.extend(data["payments"])
        event_ids.extend(item["id"] for item in data["events"])
    assert len({item["id"] for item in seen}) == len(seen) == 205
    assert sum(int(item["amount_cents"]) for item in seen) == 205
    assert len(set(event_ids)) == len(event_ids) == data["history"]["events"]["total"]
    assert client.get(f"/api/v2/receivables/{title.id}?page_size=101").status_code == 422
    # Existing clients keep their explicit v1 history contract.
    legacy = client.get(f"/api/v1/receivables/{title.id}").json()
    assert len(legacy["payments"]) == 205 and "history" not in legacy
