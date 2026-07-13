"""Password hashing (argon2) and RS256 token issuance."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.keys import get_key_manager

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(
    *, user_id: str, user_type: str, roles: list[str], tenant_id: str | None
) -> str:
    """tenant_id=None issues a *global* token (mobile-app actors). Downstream
    services treat the absent claim as "no tenant scope", never as a wildcard."""
    km = get_key_manager()
    now = datetime.now(timezone.utc)
    claims = {
        "sub": user_id,
        "user_type": user_type,
        "roles": roles,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES),
        "jti": str(uuid.uuid4()),
    }
    if tenant_id is not None:
        claims["tenant_id"] = tenant_id
    return jwt.encode(claims, km.private_pem, algorithm="RS256", headers={"kid": km.kid})


def decode_access_token(token: str) -> dict:
    """IAM verifying its own tokens (for its admin endpoints)."""
    km = get_key_manager()
    return jwt.decode(
        token,
        km.jwks,
        algorithms=["RS256"],
        issuer=settings.JWT_ISSUER,
        audience=settings.JWT_AUDIENCE,
    )


def new_refresh_token() -> tuple[str, str]:
    """Returns (raw_token, sha256_hash). Only the hash is stored."""
    raw = secrets.token_urlsafe(48)
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
