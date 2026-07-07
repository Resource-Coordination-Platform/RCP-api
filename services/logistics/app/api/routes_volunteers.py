import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_principal, require_roles
from app.core.auth import Principal
from app.db.database import get_db
from app.models import TaskStatus
from app.schemas.task_schema import DispatchTaskCreate, DispatchTaskRead
from app.services import dispatch as dispatch_service

router = APIRouter(prefix="/api/volunteers", tags=["volunteers"])


@router.get("/available")
def find_volunteers(
    skill: str | None = None,
    area: str | None = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("tenant_admin", "coordinator")),
):
    return dispatch_service.find_available_volunteers(
        db, principal.tenant_id, skill=skill, area=area
    )


@router.post("/tasks", response_model=DispatchTaskRead, status_code=status.HTTP_201_CREATED)
def dispatch_task(
    data: DispatchTaskCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("tenant_admin", "coordinator")),
):
    try:
        return dispatch_service.assign_task(db, principal, data)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.patch("/tasks/{task_id}/status", response_model=DispatchTaskRead)
def update_task(
    task_id: uuid.UUID,
    new_status: TaskStatus,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
):
    try:
        return dispatch_service.update_task_status(db, principal.tenant_id, task_id, new_status)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
