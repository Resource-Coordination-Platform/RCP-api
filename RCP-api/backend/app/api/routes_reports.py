"""Reporting & Analytics service endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.database import get_db
from app.models import User, UserRole
from app.services import reporting as reporting_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/need-vs-fulfillment")
def need_vs_fulfillment(
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(UserRole.TENANT_ADMIN, UserRole.COORDINATOR)
    ),
):
    return reporting_service.need_vs_fulfillment(db, user.tenant_id)


@router.get("/request-summary")
def request_summary(
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(UserRole.TENANT_ADMIN, UserRole.COORDINATOR)
    ),
):
    return reporting_service.request_status_summary(db, user.tenant_id)
