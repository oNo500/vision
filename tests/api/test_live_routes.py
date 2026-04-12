"""Tests for /live HTTP endpoints."""
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport


@pytest_asyncio.fixture
async def client():
    from src.api.main import create_app
    app = create_app()
    # Provide mock state directly — bypass lifespan
    app.state.session_manager = MagicMock()
    app.state.event_bus = MagicMock()
    app.state.db = AsyncMock()
    app.state.db.get_history = AsyncMock(return_value=[])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Attach app reference so tests can mutate state
        c.app = app
        yield c


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_start_agent(client):
    client.app.state.session_manager.start = MagicMock()
    client.app.state.session_manager.get_state = MagicMock(return_value={"running": True})
    resp = await client.post("/live/start", json={"mock": True})
    assert resp.status_code == 200
    assert resp.json()["running"] is True


@pytest.mark.asyncio
async def test_start_agent_already_running(client):
    client.app.state.session_manager.start = MagicMock(side_effect=RuntimeError("already running"))
    resp = await client.post("/live/start", json={"mock": True})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_stop_agent(client):
    client.app.state.session_manager.stop = MagicMock()
    client.app.state.session_manager.get_state = MagicMock(return_value={"running": False})
    resp = await client.post("/live/stop")
    assert resp.status_code == 200
    assert resp.json()["running"] is False


@pytest.mark.asyncio
async def test_stop_agent_not_running(client):
    client.app.state.session_manager.stop = MagicMock(side_effect=RuntimeError("not running"))
    resp = await client.post("/live/stop")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_state(client):
    client.app.state.session_manager.get_state = MagicMock(return_value={"running": False})
    resp = await client.get("/live/state")
    assert resp.status_code == 200
    assert resp.json()["running"] is False


@pytest.mark.asyncio
async def test_inject(client):
    client.app.state.session_manager.inject = MagicMock()
    resp = await client.post("/live/inject", json={"content": "hello"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_inject_not_running(client):
    client.app.state.session_manager.inject = MagicMock(side_effect=RuntimeError("not running"))
    resp = await client.post("/live/inject", json={"content": "hello"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_history(client):
    client.app.state.db.get_history = AsyncMock(return_value=[
        {"type": "tts_output", "content": "hi", "ts": 1000.0}
    ])
    resp = await client.get("/live/history?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["type"] == "tts_output"
