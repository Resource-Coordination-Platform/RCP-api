"""Auth dependencies for IAM's own protected endpoints.

IAM is the token issuer, so it verifies its own bearer tokens directly with
the signing key manager rather than fetching JWKS over HTTP like the other
services do.
"""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str | None
    user_type: str | None
    roles: tuple[str, ...]


def current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = decode_access_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Principal(
        user_id=claims["sub"],
        tenant_id=claims.get("tenant_id"),
        user_type=claims.get("user_type"),
        roles=tuple(claims.get("roles", [])),
    )


def require_super_admin(
    principal: Principal = Depends(current_principal),
) -> Principal:
    if "super_admin" not in principal.roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Super admin access required")
    return principal
