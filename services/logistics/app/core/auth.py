"""JWT verification for logistics.

The actual JWKS fetch/cache/verify implementation lives in
packages/common (rcp_common.auth); this module only binds it to this
service's settings and re-exports the names the rest of the app uses.
"""

from rcp_common.auth import AuthError, JWKSVerifier, Principal

from app.core.config import settings

__all__ = ["AuthError", "Principal", "verifier", "verify_token"]

verifier = JWKSVerifier(
    jwks_url=settings.JWT_JWKS_URL,
    issuer=settings.JWT_ISSUER,
    audience=settings.JWT_AUDIENCE,
    cache_ttl_seconds=settings.JWKS_CACHE_TTL_SECONDS,
)


def verify_token(token: str) -> Principal:
    return verifier.verify(token)
