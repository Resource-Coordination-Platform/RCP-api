"""Per-client token-bucket rate limiting.

In-memory: adequate for a single gateway replica. Swap the bucket store
for Redis before scaling the gateway horizontally.
"""

import threading
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings


class _Bucket:
    __slots__ = ("tokens", "updated_at")

    def __init__(self, tokens: float) -> None:
        self.tokens = tokens
        self.updated_at = time.monotonic()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def _allow(self, client_key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(client_key)
            if bucket is None:
                bucket = self._buckets[client_key] = _Bucket(float(settings.RATE_LIMIT_BURST))
            bucket.tokens = min(
                float(settings.RATE_LIMIT_BURST),
                bucket.tokens + (now - bucket.updated_at) * settings.RATE_LIMIT_RPS,
            )
            bucket.updated_at = now
            if bucket.tokens < 1.0:
                return False
            bucket.tokens -= 1.0
            return True

    async def dispatch(self, request: Request, call_next) -> Response:
        client = request.client.host if request.client else "unknown"
        if not self._allow(client):
            return JSONResponse({"detail": "Too many requests"}, status_code=429)
        return await call_next(request)
