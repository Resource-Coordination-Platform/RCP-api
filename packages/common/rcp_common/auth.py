"""Stateless JWT verification against IAM's JWKS.

Consuming services never query schema_iam. They fetch the public keys once,
cache them, and verify every request cryptographically. Refresh happens on
TTL expiry or on encountering an unknown kid (key rotation).

Extracted from the per-service vendored copies into packages/common so IAM
token verification exists exactly once.
"""

import threading
import time
import uuid
from dataclasses import dataclass

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from rcp_common.exceptions import AuthError

__all__ = [
    "AuthError",
    "JWKSVerifier",
    "Principal",
    "PrincipalDependency",
    "require_any_role",
    "require_tenant_role",
]


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    # None == global (mobile app) actor: VOLUNTEER / VICTIM / DONATOR.
    # Services must treat the absence of a tenant as "no tenant scope",
    # never as "all tenants".
    tenant_id: uuid.UUID | None
    user_type: str | None
    roles: tuple[str, ...]

    @property
    def is_global(self) -> bool:
        return self.tenant_id is None


class _JWKSCache:
    def __init__(self, jwks_url: str, cache_ttl_seconds: int) -> None:
        self._jwks_url = jwks_url
        self._ttl = cache_ttl_seconds
        self._keys: dict[str, dict] = {}
        self._fetched_at: float = 0.0
        self._lock = threading.Lock()

    def _fetch(self) -> None:
        response = httpx.get(self._jwks_url, timeout=5.0)
        response.raise_for_status()
        self._keys = {k["kid"]: k for k in response.json()["keys"]}
        self._fetched_at = time.monotonic()

    def get_key(self, kid: str) -> dict | None:
        with self._lock:
            stale = time.monotonic() - self._fetched_at > self._ttl
            if stale or (kid not in self._keys and time.monotonic() - self._fetched_at > 5):
                # refresh on TTL or unknown kid (rate-limited to avoid stampede)
                self._fetch()
            return self._keys.get(kid)


class JWKSVerifier:
    def __init__(
        self,
        jwks_url: str,
        issuer: str,
        audience: str,
        cache_ttl_seconds: int = 600,
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        self._jwks = _JWKSCache(jwks_url, cache_ttl_seconds)

    def verify(self, token: str) -> Principal:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256":  # algorithm allow-list
                raise AuthError("Disallowed algorithm")
            key = self._jwks.get_key(header.get("kid", ""))
            if key is None:
                raise AuthError("Unknown signing key")
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self._issuer,
                audience=self._audience,
            )
            raw_tenant = claims.get("tenant_id")
            return Principal(
                user_id=uuid.UUID(claims["sub"]),
                tenant_id=uuid.UUID(raw_tenant) if raw_tenant else None,
                user_type=claims.get("user_type"),
                roles=tuple(claims.get("roles", [])),
            )
        except (JWTError, KeyError, ValueError, httpx.HTTPError) as exc:
            raise AuthError(str(exc)) from exc


_bearer = HTTPBearer(auto_error=False)


class PrincipalDependency:
    """FastAPI dependency: resolve the bearer token into a Principal."""

    def __init__(self, verifier: JWKSVerifier) -> None:
        self._verifier = verifier

    def __call__(
        self,
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ) -> Principal:
        if credentials is None:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Missing bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            return self._verifier.verify(credentials.credentials)
        except AuthError:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )


def require_any_role(principal_dependency: PrincipalDependency, *roles: str):
    def checker(principal: Principal = Depends(principal_dependency)) -> Principal:
        if not set(roles) & set(principal.roles):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return principal

    return checker


def require_tenant_role(principal_dependency: PrincipalDependency, *roles: str):
    """Like require_any_role, but additionally rejects global (tenant-less)
    principals — for endpoints whose data is tenant-scoped."""

    def checker(principal: Principal = Depends(principal_dependency)) -> Principal:
        if principal.tenant_id is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Tenant-scoped endpoint")
        if not set(roles) & set(principal.roles):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return principal

    return checker
