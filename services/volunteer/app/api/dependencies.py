from rcp_common.auth import PrincipalDependency, require_any_role, require_tenant_role

from app.core.auth import verifier

get_principal = PrincipalDependency(verifier)


def require_roles(*roles: str):
    return require_any_role(get_principal, *roles)


def require_tenant_roles(*roles: str):
    """Tenant-scoped guard: also rejects global (mobile) principals."""
    return require_tenant_role(get_principal, *roles)
