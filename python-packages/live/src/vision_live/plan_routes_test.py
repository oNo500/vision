"""Integration tests for /live/plans routes."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app


@pytest.fixture
def client(tmp_path):
    import os
    os.environ["VISION_DB_PATH"] = str(tmp_path / "test.db")
    # Clear lru_cache so settings picks up the new env var
    from src.api.settings import get_settings
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    get_settings.cache_clear()


def _create_plan(client: TestClient, name: str = "Test Plan") -> dict:
    resp = client.post("/live/plans", json={
        "name": name,
        "product": {"name": "P", "description": "D", "price": "99",
                    "highlights": [], "faq": []},
        "persona": {"name": "主播", "style": "friendly",
                    "catchphrases": [], "forbidden_words": []},
        "script": {"segments": []},
    })
    assert resp.status_code == 201
    return resp.json()


def test_create_and_get(client: TestClient):
    plan = _create_plan(client)
    assert plan["id"]
    resp = client.get(f"/live/plans/{plan['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Plan"


def test_list(client: TestClient):
    _create_plan(client, "A")
    _create_plan(client, "B")
    resp = client.get("/live/plans")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert "product" not in data[0]


def test_update(client: TestClient):
    plan = _create_plan(client)
    resp = client.put(f"/live/plans/{plan['id']}", json={**plan, "name": "Renamed"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"


def test_delete(client: TestClient):
    plan = _create_plan(client)
    resp = client.delete(f"/live/plans/{plan['id']}")
    assert resp.status_code == 204
    resp2 = client.get(f"/live/plans/{plan['id']}")
    assert resp2.status_code == 404


def test_get_not_found(client: TestClient):
    resp = client.get("/live/plans/nonexistent")
    assert resp.status_code == 404


def test_active_plan_none_initially(client: TestClient):
    resp = client.get("/live/plans/active")
    assert resp.status_code == 200
    assert resp.json() == {"plan": None}


def test_load_plan(client: TestClient):
    plan = _create_plan(client)
    resp = client.post(f"/live/plans/{plan['id']}/load")
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"]["id"] == plan["id"]
    # Now GET /active should return the loaded plan
    active_resp = client.get("/live/plans/active")
    assert active_resp.status_code == 200
    assert active_resp.json()["plan"]["id"] == plan["id"]


def test_load_plan_not_found(client: TestClient):
    resp = client.post("/live/plans/nonexistent/load")
    assert resp.status_code == 404


def test_delete_active_plan_returns_409(client: TestClient):
    plan = _create_plan(client)
    client.post(f"/live/plans/{plan['id']}/load")
    resp = client.delete(f"/live/plans/{plan['id']}")
    assert resp.status_code == 409


def test_delete_nonexistent_plan_returns_404(client: TestClient):
    resp = client.delete("/live/plans/nonexistent")
    assert resp.status_code == 404


def test_update_nonexistent_plan_returns_404(client: TestClient):
    resp = client.put("/live/plans/nonexistent", json={
        "name": "X",
        "product": {"name": "", "description": "", "price": "", "highlights": [], "faq": []},
        "persona": {"name": "", "style": "", "catchphrases": [], "forbidden_words": []},
        "script": {"segments": []},
    })
    assert resp.status_code == 404
