"""Assignment endpoints — mobile app, VOLUNTEER actors.

Accept is the first-come-first-serve moment: a 409 means the skill
bucket filled before this volunteer tapped Accept.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from rcp_common.auth import Principal
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.database import get_db
from app.models import AssignmentStatus, EventVolunteerMapping, VolunteerProfile
from app.schemas.event_schema import AssignmentRead
from app.services.matching import AssignmentError, QuotaFullError, accept_assignment, transition_assignment

router = APIRouter(prefix="/api/volunteer/assignments", tags=["assignments"])

_volunteer = require_roles("volunteer")


@router.get("", response_model=list[AssignmentRead])
def my_assignments(
    principal: Principal = Depends(_volunteer),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(EventVolunteerMapping)
        .join(VolunteerProfile, VolunteerProfile.id == EventVolunteerMapping.volunteer_id)
        .where(VolunteerProfile.user_id == principal.user_id)
        .order_by(EventVolunteerMapping.created_at.desc())
    ).all()

            
@router.post("/{assignment_id}/accept", response_model=AssignmentRead)
def accept(
    assignment_id: uuid.UUID,
    principal: Principal = Depends(_volunteer),
    db: Session = Depends(get_db),
):
    try:
        return accept_assignment(
            db, mapping_id=assignment_id, volunteer_user_id=principal.user_id
        )
    except QuotaFullError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    except AssignmentError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


def _transition(db: Session, assignment_id: uuid.UUID, principal: Principal, to: AssignmentStatus):
    try:
        return transition_assignment(
            db,
            mapping_id=assignment_id,
            volunteer_user_id=principal.user_id,
            new_status=to,
        )
    except AssignmentError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.post("/{assignment_id}/decline", response_model=AssignmentRead)
def decline(
    assignment_id: uuid.UUID,
    principal: Principal = Depends(_volunteer),
    db: Session = Depends(get_db),
):
    return _transition(db, assignment_id, principal, AssignmentStatus.DECLINED)


@router.post("/{assignment_id}/en-route", response_model=AssignmentRead)
def en_route(
    assignment_id: uuid.UUID,
    principal: Principal = Depends(_volunteer),
    db: Session = Depends(get_db),
):
    return _transition(db, assignment_id, principal, AssignmentStatus.EN_ROUTE)


@router.post("/{assignment_id}/complete", response_model=AssignmentRead)
def complete(
    assignment_id: uuid.UUID,
    principal: Principal = Depends(_volunteer),
    db: Session = Depends(get_db),
):
    return _transition(db, assignment_id, principal, AssignmentStatus.COMPLETED)
