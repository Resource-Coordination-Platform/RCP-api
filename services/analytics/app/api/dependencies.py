from rcp_common.auth import JWKSVerifier, PrincipalDependency, require_any_role

from app.core.config import settings

_verifier = JWKSVerifier(
    jwks_url=settings.JWT_JWKS_URL,
    issuer=settings.JWT_ISSUER,
    audience=settings.JWT_AUDIENCE,
    cache_ttl_seconds=settings.JWKS_CACHE_TTL_SECONDS,
)

get_principal = PrincipalDependency(_verifier)


def require_roles(*roles: str):
    return require_any_role(get_principal, *roles)
