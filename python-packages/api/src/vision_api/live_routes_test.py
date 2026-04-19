"""Tests for /live HTTP endpoints."""
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport


@pytest_asyncio.fixture
async def client():
    from vision_api.main import create_app
    app = create_app()
    # Provide mock state directly — bypass lifespan
    app.state.session_manager = MagicMock()
    app.state.danmaku_manager = MagicMock()
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
    from vision_live.session import SessionAlreadyRunningError
    client.app.state.session_manager.start = MagicMock(side_effect=SessionAlreadyRunningError("Session already running"))
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


@pytest.mark.asyncio
async def test_script_next_returns_400_when_not_running(client):
    client.app.state.session_manager.get_script_runner = MagicMock(return_value=None)
    resp = await client.post("/live/script/next")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Session not running"


@pytest.mark.asyncio
async def test_script_prev_returns_400_when_not_running(client):
    client.app.state.session_manager.get_script_runner = MagicMock(return_value=None)
    resp = await client.post("/live/script/prev")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Session not running"


@pytest.mark.asyncio
async def test_session_start(client):
    client.app.state.session_manager.start = MagicMock()
    client.app.state.session_manager.get_state = MagicMock(return_value={"running": True, "strategy": "immediate"})
    resp = await client.post("/live/session/start", json={"mock": True})
    assert resp.status_code == 200
    assert resp.json()["running"] is True
    assert "strategy" in resp.json()


@pytest.mark.asyncio
async def test_session_stop(client):
    client.app.state.session_manager.stop = MagicMock()
    client.app.state.session_manager.get_state = MagicMock(return_value={"running": False, "strategy": "immediate"})
    resp = await client.post("/live/session/stop")
    assert resp.status_code == 200
    assert resp.json()["running"] is False


@pytest.mark.asyncio
async def test_session_start_twice_returns_409(client):
    from vision_live.session import SessionAlreadyRunningError
    client.app.state.session_manager.start = MagicMock(side_effect=SessionAlreadyRunningError("already running"))
    resp = await client.post("/live/session/start", json={"mock": True})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_session_state(client):
    client.app.state.session_manager.get_state = MagicMock(return_value={"running": False, "strategy": "immediate"})
    resp = await client.get("/live/session/state")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_danmaku_start(client):
    client.app.state.danmaku_manager.start = MagicMock()
    client.app.state.session_manager.get_tts_queue = MagicMock(return_value=None)
    client.app.state.session_manager.get_urgent_queue = MagicMock(return_value=None)
    client.app.state.session_manager.get_strategy = MagicMock(return_value="immediate")
    client.app.state.danmaku_manager.get_state = MagicMock(return_value={"running": True, "buffer_size": 0})
    resp = await client.post("/live/danmaku/start", json={"mock": True})
    assert resp.status_code == 200
    assert resp.json()["running"] is True


@pytest.mark.asyncio
async def test_danmaku_stop(client):
    client.app.state.danmaku_manager.stop = MagicMock()
    client.app.state.danmaku_manager.get_state = MagicMock(return_value={"running": False, "buffer_size": 0})
    resp = await client.post("/live/danmaku/stop")
    assert resp.status_code == 200
    assert resp.json()["running"] is False


@pytest.mark.asyncio
async def test_danmaku_state(client):
    client.app.state.danmaku_manager.get_state = MagicMock(return_value={"running": False, "buffer_size": 0})
    resp = await client.get("/live/danmaku/state")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_strategy(client):
    client.app.state.session_manager.get_strategy = MagicMock(return_value="immediate")
    resp = await client.get("/live/strategy")
    assert resp.status_code == 200
    assert resp.json()["strategy"] == "immediate"


@pytest.mark.asyncio
async def test_set_strategy(client):
    client.app.state.session_manager.set_strategy = MagicMock()
    client.app.state.session_manager.get_strategy = MagicMock(return_value="intelligent")
    resp = await client.post("/live/strategy", json={"strategy": "intelligent"})
    assert resp.status_code == 200
    assert resp.json()["strategy"] == "intelligent"


@pytest.mark.asyncio
async def test_set_invalid_strategy_returns_400(client):
    client.app.state.session_manager.set_strategy = MagicMock(side_effect=ValueError("Unknown strategy"))
    resp = await client.post("/live/strategy", json={"strategy": "unknown"})
    assert resp.status_code == 400


@pytest_asyncio.fixture
async def plan_client(tmp_path):
    import aiosqlite
    from vision_api.main import create_app
    from vision_live.plan_store import PlanStore
    from vision_shared.db import Database

    db_path = str(tmp_path / "test.db")
    from vision_api.settings import get_settings
    get_settings.cache_clear()
    import os
    os.environ["VISION_DB_PATH"] = db_path
    get_settings.cache_clear()

    app = create_app()
    app.state.session_manager = MagicMock()
    app.state.danmaku_manager = MagicMock()
    app.state.event_bus = MagicMock()

    conn = await aiosqlite.connect(db_path)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS live_plans (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    await conn.commit()
    app.state.plan_store = PlanStore(conn)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        c.app = app
        yield c

    await conn.close()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_put_plan_rag_libraries(plan_client):
    r = await plan_client.post("live/plans", json={"name": "Test"})
    assert r.status_code == 201
    plan_id = r.json()["id"]

    r = await plan_client.put(
        f"live/plans/{plan_id}/rag-libraries",
        json={"library_ids": ["dong-yuhui", "li-jiaqi"]},
    )
    assert r.status_code == 200
    assert r.json()["rag_library_ids"] == ["dong-yuhui", "li-jiaqi"]


@pytest.mark.asyncio
async def test_put_plan_rag_libraries_replaces(plan_client):
    r = await plan_client.post("live/plans", json={"name": "Test"})
    plan_id = r.json()["id"]
    await plan_client.put(f"live/plans/{plan_id}/rag-libraries", json={"library_ids": ["a"]})
    r = await plan_client.put(f"live/plans/{plan_id}/rag-libraries", json={"library_ids": ["b"]})
    assert r.json()["rag_library_ids"] == ["b"]
