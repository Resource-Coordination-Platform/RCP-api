from rcp_common.auth import PrincipalDependency, require_any_role

from app.core.auth import verifier

get_principal = PrincipalDependency(verifier)


def require_roles(*roles: str):
    return require_any_role(get_principal, *roles)
