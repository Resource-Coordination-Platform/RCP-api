from fastapi import APIRouter, Depends
from rcp_common.auth import Principal
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.database import get_db
from app.services import reporting as reporting_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/need-vs-fulfillment")
def need_vs_fulfillment(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("tenant_admin", "coordinator")),
):
    return reporting_service.need_vs_fulfillment(db, principal.tenant_id)


@router.get("/request-summary")
def request_summary(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("tenant_admin", "coordinator")),
):
    return reporting_service.request_status_summary(db, principal.tenant_id)
