import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from rcp_common.exceptions import ConflictError, NotFoundError
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
from app.services.form_schema import FormValidationError

router = APIRouter(prefix="/api/requests", tags=["requests"])


@router.post("", response_model=HelpRequestRead, status_code=status.HTTP_201_CREATED)
def submit_request(
    data: HelpRequestCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
):
    try:
        return request_service.create_request(db, principal, data)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except ConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    except FormValidationError as exc:
        # per-field detail so the admin-defined form can highlight the inputs
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {"message": "extra_fields does not match the category form", "errors": exc.errors},
        )


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
