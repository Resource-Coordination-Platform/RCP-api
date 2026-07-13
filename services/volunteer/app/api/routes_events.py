"""Disaster event endpoints — web portal, tenant-bound actors only.

Declaring an event returns immediately; the matching fan-out happens
asynchronously when the disaster consumer picks up
`volunteer.disaster.declared`.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from rcp_common.auth import Principal
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import require_tenant_roles
from app.db.database import get_db
from app.domain.districts import ADJACENCY
from app.models import DisasterEvent, EventStatus
from app.schemas.event_schema import DisasterEventCreate, DisasterEventRead
from app.services import matching

router = APIRouter(prefix="/api/volunteer/events", tags=["disaster-events"])

_portal = require_tenant_roles("tenant_admin", "coordinator")


@router.get("/districts")
def list_districts():
    """The static geography clients build broadcast UIs from."""
    return {d: sorted(n) for d, n in sorted(ADJACENCY.items())}


@router.post("", response_model=DisasterEventRead, status_code=status.HTTP_201_CREATED)
def declare_event(
    data: DisasterEventCreate,
    principal: Principal = Depends(_portal),
    db: Session = Depends(get_db),
):
    return matching.declare_event(
        db, tenant_id=principal.tenant_id, created_by=principal.user_id, data=data
    )


@router.get("", response_model=list[DisasterEventRead])
def list_events(
    principal: Principal = Depends(_portal),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(DisasterEvent)
        .where(DisasterEvent.tenant_id == principal.tenant_id)
        .options(selectinload(DisasterEvent.requirements))
        .order_by(DisasterEvent.created_at.desc())
    ).all()


def _tenant_event(db: Session, principal: Principal, event_id: uuid.UUID) -> DisasterEvent:
    event = db.scalars(
        select(DisasterEvent)
        .where(DisasterEvent.id == event_id, DisasterEvent.tenant_id == principal.tenant_id)
        .options(selectinload(DisasterEvent.requirements))
    ).first()
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    return event


@router.get("/{event_id}", response_model=DisasterEventRead)
def read_event(
    event_id: uuid.UUID,
    principal: Principal = Depends(_portal),
    db: Session = Depends(get_db),
):
    return _tenant_event(db, principal, event_id)


@router.post("/{event_id}/rebroadcast", response_model=DisasterEventRead)
def rebroadcast(
    event_id: uuid.UUID,
    principal: Principal = Depends(_portal),
    db: Session = Depends(get_db),
):
    """Re-run matching for still-open buckets (e.g. after volunteers
    declined, or new volunteers became available)."""
    event = _tenant_event(db, principal, event_id)
    if event.status not in (EventStatus.DECLARED, EventStatus.BROADCASTING):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Event is {event.status.value}")
    matching.run_matching(db, event.id)
    db.refresh(event)
    return event


@router.post("/{event_id}/close", response_model=DisasterEventRead)
def close_event(
    event_id: uuid.UUID,
    principal: Principal = Depends(_portal),
    db: Session = Depends(get_db),
):
    event = _tenant_event(db, principal, event_id)
    event.status = EventStatus.CLOSED
    db.commit()
    db.refresh(event)
    return event
