from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_create_and_get_prospect():
    payload = {
        "company_name": "Acme Corp",
        "industry": "tech",
        "contact_name": "Alice",
        "email": "alice@example.com",
        "phone": "+100000000",
        "engagement_level": "low",
        "notes": "test",
        "preferred_channel": "email",
        "objections": []
    }
    r = client.post("/prospects/", json=payload)
    assert r.status_code == 200
    pid = r.json()["prospect_id"]

    r2 = client.get(f"/prospects/{pid}")
    assert r2.status_code == 200
    got = r2.json()
    assert got["company_name"] == "Acme Corp"

    r3 = client.get(f"/prospects/{pid}/history")
    assert r3.status_code == 200
    assert isinstance(r3.json(), list)
