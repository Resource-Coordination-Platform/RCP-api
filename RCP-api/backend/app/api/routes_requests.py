"""Request & Needs Management service endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_roles
from app.db.database import get_db
from app.models import RequestStatus, User, UserRole
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
    user: User = Depends(get_current_user),
):
    """Public portal: 'Request Help'."""
    return request_service.create_request(db, user.tenant_id, data, requester=user)


@router.get("", response_model=list[HelpRequestRead])
def list_requests(
    status_filter: RequestStatus | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(UserRole.TENANT_ADMIN, UserRole.COORDINATOR)
    ),
):
    """Coordinator dashboard: triage queue ordered by urgency."""
    return request_service.list_requests(
        db, user.tenant_id, status=status_filter, limit=limit, offset=offset
    )


@router.patch("/{request_id}/status", response_model=HelpRequestRead)
def update_status(
    request_id: uuid.UUID,
    data: HelpRequestStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(UserRole.TENANT_ADMIN, UserRole.COORDINATOR)
    ),
):
    """Verify / approve / reject a request (lifecycle transition)."""
    request = request_service.get_request(db, user.tenant_id, request_id)
    if request is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    try:
        return request_service.change_status(db, request, data.status, actor=user)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
