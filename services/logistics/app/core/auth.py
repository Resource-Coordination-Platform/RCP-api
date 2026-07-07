"""Stateless JWT verification against IAM's JWKS.

This service never queries schema_iam. It fetches the public keys once,
caches them, and verifies every request cryptographically. Refresh
happens on TTL expiry or on encountering an unknown kid (key rotation).
"""

import threading
import time
import uuid
from dataclasses import dataclass

import httpx
from jose import JWTError, jwt

from app.core.config import settings


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    roles: tuple[str, ...]


class JWKSCache:
    def __init__(self) -> None:
        self._keys: dict[str, dict] = {}
        self._fetched_at: float = 0.0
        self._lock = threading.Lock()

    def _fetch(self) -> None:
        response = httpx.get(settings.JWT_JWKS_URL, timeout=5.0)
        response.raise_for_status()
        self._keys = {k["kid"]: k for k in response.json()["keys"]}
        self._fetched_at = time.monotonic()

    def get_key(self, kid: str) -> dict | None:
        with self._lock:
            stale = time.monotonic() - self._fetched_at > settings.JWKS_CACHE_TTL_SECONDS
            if stale or (kid not in self._keys and time.monotonic() - self._fetched_at > 5):
                # refresh on TTL or unknown kid (rate-limited to avoid stampede)
                self._fetch()
            return self._keys.get(kid)


_jwks = JWKSCache()


class AuthError(Exception):
    pass


def verify_token(token: str) -> Principal:
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256":  # algorithm allow-list
            raise AuthError("Disallowed algorithm")
        key = _jwks.get_key(header.get("kid", ""))
        if key is None:
            raise AuthError("Unknown signing key")
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
        )
        return Principal(
            user_id=uuid.UUID(claims["sub"]),
            tenant_id=uuid.UUID(claims["tenant_id"]),
            roles=tuple(claims.get("roles", [])),
        )
    except (JWTError, KeyError, ValueError, httpx.HTTPError) as exc:
        raise AuthError(str(exc)) from exc
