"""Volunteer Dispatch & Task service endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_roles
from app.db.database import get_db
from app.models import TaskStatus, User, UserRole
from app.schemas.task_schema import DispatchTaskCreate, DispatchTaskRead
from app.services import dispatch as dispatch_service

router = APIRouter(prefix="/api/volunteers", tags=["volunteers"])


@router.get("/available")
def find_volunteers(
    skill: str | None = None,
    area: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(UserRole.TENANT_ADMIN, UserRole.COORDINATOR)
    ),
):
    volunteers = dispatch_service.find_available_volunteers(
        db, user.tenant_id, skill_name=skill, area=area
    )
    return [
        {
            "id": str(v.id),
            "name": v.user.full_name,
            "area": v.area,
            "skills": [s.name for s in v.skills],
        }
        for v in volunteers
    ]


@router.post("/tasks", response_model=DispatchTaskRead, status_code=status.HTTP_201_CREATED)
def dispatch_task(
    data: DispatchTaskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(UserRole.TENANT_ADMIN, UserRole.COORDINATOR)
    ),
):
    try:
        return dispatch_service.assign_task(db, user.tenant_id, data, assigned_by=user)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.patch("/tasks/{task_id}/status", response_model=DispatchTaskRead)
def update_task(
    task_id: uuid.UUID,
    new_status: TaskStatus,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return dispatch_service.update_task_status(db, user.tenant_id, task_id, new_status)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
