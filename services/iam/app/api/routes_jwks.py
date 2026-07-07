from fastapi import APIRouter

from app.core.keys import get_key_manager

router = APIRouter(tags=["jwks"])


@router.get("/.well-known/jwks.json")
def jwks():
    """Public verification keys. Logistics and RTO cache this document and
    verify every JWT locally — no service ever queries schema_iam."""
    return get_key_manager().jwks
