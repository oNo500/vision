"""X-API-Key middleware protecting POST/PUT/DELETE on /api/*."""
from __future__ import annotations

from typing import Sequence

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


_PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, api_key: str, protected_prefixes: Sequence[str]) -> None:
        super().__init__(app)
        self._key = api_key
        self._prefixes = tuple(protected_prefixes)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in _PROTECTED_METHODS and \
           any(request.url.path.startswith(p) for p in self._prefixes):
            header = request.headers.get("x-api-key")
            if not header:
                return JSONResponse({"detail": "missing X-API-Key"}, status_code=401)
            if header != self._key:
                return JSONResponse({"detail": "invalid X-API-Key"}, status_code=403)
        return await call_next(request)
