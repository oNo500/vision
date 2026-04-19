from fastapi import FastAPI
from fastapi.testclient import TestClient

from vision_api.api_key import ApiKeyMiddleware


def _build(api_key: str = "secret"):
    app = FastAPI()
    app.add_middleware(ApiKeyMiddleware, api_key=api_key,
                       protected_prefixes=("/api/intelligence/",))
    @app.post("/api/intelligence/foo")
    def foo(): return {"ok": True}
    @app.get("/api/intelligence/foo")
    def foo_get(): return {"ok": True}
    @app.get("/health")
    def health(): return {"ok": True}
    return app


def test_protected_write_requires_key():
    app = _build()
    c = TestClient(app)
    assert c.post("/api/intelligence/foo").status_code == 401
    assert c.post("/api/intelligence/foo",
                  headers={"X-API-Key": "wrong"}).status_code == 403
    assert c.post("/api/intelligence/foo",
                  headers={"X-API-Key": "secret"}).status_code == 200


def test_protected_read_allowed_without_key():
    app = _build()
    c = TestClient(app)
    assert c.get("/api/intelligence/foo").status_code == 200


def test_unprotected_path_allowed():
    app = _build()
    c = TestClient(app)
    assert c.get("/health").status_code == 200
    assert c.post("/health").status_code == 405  # method not allowed, but not blocked
