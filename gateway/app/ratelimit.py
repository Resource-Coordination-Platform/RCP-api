"""Per-client token-bucket rate limiting.

Uses Redis when REDIS_URL is configured; otherwise falls back to in-memory
for local development.
"""

import threading
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

try:
    import redis.asyncio as redis
except Exception:  # pragma: no cover - optional dependency
    redis = None

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
        self._redis = None
        if settings.REDIS_URL and redis is not None:
            self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

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

    async def _allow_redis(self, client_key: str) -> bool:
        assert self._redis is not None
        now = time.time()
        key = f"rate-limit:{client_key}"
        lua = """
        local key = KEYS[1]
        local burst = tonumber(ARGV[1])
        local rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local data = redis.call('HMGET', key, 'tokens', 'updated_at')
        local tokens = tonumber(data[1])
        local updated_at = tonumber(data[2])
        if tokens == nil then tokens = burst end
        if updated_at == nil then updated_at = now end
        local filled = math.min(burst, tokens + (now - updated_at) * rate)
        if filled < 1 then
          redis.call('HMSET', key, 'tokens', filled, 'updated_at', now)
          redis.call('EXPIRE', key, 120)
          return 0
        end
        redis.call('HMSET', key, 'tokens', filled - 1, 'updated_at', now)
        redis.call('EXPIRE', key, 120)
        return 1
        """
        result = await self._redis.eval(
            lua,
            1,
            key,
            float(settings.RATE_LIMIT_BURST),
            float(settings.RATE_LIMIT_RPS),
            now,
        )
        return bool(int(result))

    @staticmethod
    def _client_key(request: Request) -> str:
        if settings.RATE_LIMIT_TRUST_FORWARDED:
            forwarded = request.headers.get("x-forwarded-for", "")
            if forwarded:
                # leftmost entry = original client, as written by the trusted
                # edge hop; only honored when explicitly enabled
                return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next) -> Response:
        client = self._client_key(request)
        if self._redis is not None:
            allowed = await self._allow_redis(client)
        else:
            allowed = self._allow(client)
        if not allowed:
            return JSONResponse({"detail": "Too many requests"}, status_code=429)
        return await call_next(request)
