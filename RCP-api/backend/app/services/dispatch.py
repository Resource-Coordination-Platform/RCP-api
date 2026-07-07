"""Volunteer Dispatch & Task service logic (ORM examples):
find suitable volunteers and assign tasks for verified requests."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AvailabilityStatus,
    DispatchTask,
    HelpRequest,
    Notification,
    NotificationType,
    RequestStatus,
    Skill,
    TaskStatus,
    User,
    VolunteerProfile,
)
from app.schemas.task_schema import DispatchTaskCreate


def find_available_volunteers(
    db: Session,
    tenant_id: uuid.UUID,
    skill_name: str | None = None,
    area: str | None = None,
) -> list[VolunteerProfile]:
    """Match volunteers by availability, skill, and coarse location."""
    stmt = (
        select(VolunteerProfile)
        .where(
            VolunteerProfile.tenant_id == tenant_id,
            VolunteerProfile.availability == AvailabilityStatus.AVAILABLE,
        )
        .options(selectinload(VolunteerProfile.skills), selectinload(VolunteerProfile.user))
    )
    if skill_name:
        stmt = stmt.join(VolunteerProfile.skills).where(Skill.name == skill_name)
    if area:
        stmt = stmt.where(VolunteerProfile.area.ilike(f"%{area}%"))
    return list(db.scalars(stmt).unique())


def assign_task(
    db: Session,
    tenant_id: uuid.UUID,
    data: DispatchTaskCreate,
    assigned_by: User,
) -> DispatchTask:
    request = db.get(HelpRequest, data.request_id)
    if request is None or request.tenant_id != tenant_id:
        raise ValueError("Request not found")
    if request.status not in (RequestStatus.APPROVED, RequestStatus.IN_PROGRESS):
        raise ValueError("Request must be approved before dispatching a volunteer")

    volunteer = db.get(VolunteerProfile, data.volunteer_id)
    if volunteer is None or volunteer.tenant_id != tenant_id:
        raise ValueError("Volunteer not found")

    task = DispatchTask(
        tenant_id=tenant_id,
        assigned_by_id=assigned_by.id,
        **data.model_dump(),
    )
    request.status = RequestStatus.IN_PROGRESS
    db.add(task)

    # persisted notification; the WebSocket layer pushes it live
    db.add(
        Notification(
            tenant_id=tenant_id,
            user_id=volunteer.user_id,
            type=NotificationType.TASK_ASSIGNED,
            title="New task assigned",
            body=data.title,
        )
    )
    db.commit()
    db.refresh(task)
    return task


def update_task_status(
    db: Session, tenant_id: uuid.UUID, task_id: uuid.UUID, new_status: TaskStatus
) -> DispatchTask:
    task = db.get(DispatchTask, task_id)
    if task is None or task.tenant_id != tenant_id:
        raise ValueError("Task not found")

    now = datetime.now(timezone.utc)
    task.status = new_status
    if new_status == TaskStatus.ACCEPTED:
        task.accepted_at = now
    elif new_status == TaskStatus.COMPLETED:
        task.completed_at = now

    db.commit()
    db.refresh(task)
    return task
