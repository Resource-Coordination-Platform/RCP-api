"""Volunteer dispatch. Publishes the fat logistics.task.assigned event
(names resolved from user_replicas) so RTO needs no other service."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import Principal
from app.events.publisher import emit
from app.models import (
    AvailabilityStatus,
    DispatchTask,
    HelpRequest,
    RequestStatus,
    TaskStatus,
    UserReplica,
    VolunteerProfile,
    VolunteerSkill,
)
from app.schemas.task_schema import DispatchTaskCreate


def find_available_volunteers(
    db: Session,
    tenant_id: uuid.UUID,
    skill: str | None = None,
    area: str | None = None,
) -> list[dict]:
    stmt = (
        select(VolunteerProfile)
        .where(
            VolunteerProfile.tenant_id == tenant_id,
            VolunteerProfile.availability == AvailabilityStatus.AVAILABLE,
        )
        .options(selectinload(VolunteerProfile.skills))
    )
    if skill:
        stmt = stmt.join(VolunteerProfile.skills).where(VolunteerSkill.skill == skill)
    if area:
        stmt = stmt.where(VolunteerProfile.area.ilike(f"%{area}%"))
    profiles = list(db.scalars(stmt).unique())

    # resolve display names from the local replica (never from IAM)
    replica_ids = [p.user_id for p in profiles]
    replicas = {
        r.user_id: r
        for r in db.scalars(select(UserReplica).where(UserReplica.user_id.in_(replica_ids)))
    }
    return [
        {
            "profile_id": str(p.id),
            "user_id": str(p.user_id),
            "full_name": replicas[p.user_id].full_name if p.user_id in replicas else None,
            "area": p.area,
            "skills": p.skill_names,
        }
        for p in profiles
    ]


def assign_task(
    db: Session, principal: Principal, data: DispatchTaskCreate
) -> DispatchTask:
    request = db.get(HelpRequest, data.request_id)
    if request is None or request.tenant_id != principal.tenant_id:
        raise ValueError("Request not found")
    if request.status not in (RequestStatus.APPROVED, RequestStatus.IN_PROGRESS):
        raise ValueError("Request must be approved before dispatching a volunteer")

    # Volunteer identity and operational state are owned by the volunteer
    # service (global actors); this service cannot authoritatively validate
    # the reference, so it only rejects what it *knows* is wrong — a
    # replicated user who is deactivated or isn't a volunteer. An absent
    # replica is accepted: the coordinator picked the volunteer from the
    # volunteer-service directory, and the replica may still be in flight.
    volunteer_replica = db.get(UserReplica, data.volunteer_user_id)
    if volunteer_replica is not None:
        if not volunteer_replica.is_active:
            raise ValueError("Volunteer is deactivated")
        if "volunteer" not in volunteer_replica.roles:
            raise ValueError("User is not a volunteer")

    task = DispatchTask(
        tenant_id=principal.tenant_id,
        assigned_by_user_id=principal.user_id,
        **data.model_dump(),
    )
    request.status = RequestStatus.IN_PROGRESS
    db.add(task)
    db.flush()

    assigner_replica = db.get(UserReplica, principal.user_id)
    emit(
        db,
        routing_key="logistics.task.assigned",
        tenant_id=principal.tenant_id,
        data={
            "task_id": str(task.id),
            "request_id": str(request.id),
            "title": task.title,
            "instructions": task.instructions,
            "priority": request.urgency.value,
            "category": {
                "id": str(request.category_id),
                "name": request.category.name if request.category else None,
            },
            "location": {
                "area": request.area,
                "lat": request.latitude,
                "lng": request.longitude,
            },
            "volunteer": {
                "user_id": str(data.volunteer_user_id),
                "full_name": volunteer_replica.full_name if volunteer_replica else None,
            },
            "assigned_by": {
                "user_id": str(principal.user_id),
                "full_name": assigner_replica.full_name if assigner_replica else None,
            },
            "assigned_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": None,
        },
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

    old_status = task.status
    now = datetime.now(timezone.utc)
    task.status = new_status
    if new_status == TaskStatus.ACCEPTED:
        task.accepted_at = now
    elif new_status == TaskStatus.COMPLETED:
        task.completed_at = now

    emit(
        db,
        routing_key="logistics.task.status-changed",
        tenant_id=tenant_id,
        data={
            "task_id": str(task.id),
            "request_id": str(task.request_id),
            "volunteer_user_id": str(task.volunteer_user_id),
            "old_status": old_status.value,
            "new_status": new_status.value,
        },
    )
    db.commit()
    db.refresh(task)
    return task
