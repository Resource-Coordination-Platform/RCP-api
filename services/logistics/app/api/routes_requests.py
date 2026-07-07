import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_principal, require_roles
from app.core.auth import Principal
from app.db.database import get_db
from app.models import RequestStatus
from app.schemas.request_schema import (
    HelpRequestCreate,
    HelpRequestRead,
    HelpRequestStatusUpdate,
)
from app.services import requests as request_service

router = APIRouter(prefix="/api/requests", tags=["requests"])


@router.post("", response_model=HelpRequestRead, status_code=status.HTTP_201_CREATED)
def submit_request(
    data: HelpRequestCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
):
    return request_service.create_request(db, principal, data)


@router.get("", response_model=list[HelpRequestRead])
def list_requests(
    status_filter: RequestStatus | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("tenant_admin", "coordinator")),
):
    return request_service.list_requests(
        db, principal.tenant_id, status=status_filter, limit=limit, offset=offset
    )


@router.patch("/{request_id}/status", response_model=HelpRequestRead)
def update_status(
    request_id: uuid.UUID,
    data: HelpRequestStatusUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("tenant_admin", "coordinator")),
):
    request = request_service.get_request(db, principal.tenant_id, request_id)
    if request is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    try:
        return request_service.change_status(db, request, data.status, principal)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
