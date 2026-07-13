"""Matching engine: rule-based, SQL-only volunteer team formation.

Pipeline (all steps event-driven, no cross-service calls):

1. declare_event   — API writes the DisasterEvent aggregate and emits
                     `volunteer.disaster.declared` through the outbox.
2. run_matching    — the disaster consumer resolves the district list
                     (adjacency or targeted), filters VolunteerProfile
                     with plain SQL per skill bucket, writes NOTIFIED
                     mappings and emits one `volunteer.assignment.notified`
                     per volunteer (the simulated push notification).
3. accept          — first-come-first-serve. The quota gate is a single
                     conditional UPDATE on EventRequirement; once a bucket
                     is full every later acceptance is rejected atomically.
                     When the last bucket fills, `volunteer.team.formed`
                     is emitted.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.domain.districts import resolve_broadcast_districts
from app.events.publisher import emit
from app.models import (
    AssignmentStatus,
    BroadcastType,
    DisasterEvent,
    EventRequirement,
    EventStatus,
    EventVolunteerMapping,
    RequirementStatus,
    VolunteerProfile,
)
from app.schemas.event_schema import DisasterEventCreate

log = logging.getLogger("volunteer.matching")


class AssignmentError(Exception):
    """Domain-rule violation on an assignment transition."""


class QuotaFullError(AssignmentError):
    """The skill bucket filled before this volunteer accepted."""


# ---------------------------------------------------------------- declare


def declare_event(
    db: Session, *, tenant_id: uuid.UUID, created_by: uuid.UUID, data: DisasterEventCreate
) -> DisasterEvent:
    """Persist the aggregate and emit `volunteer.disaster.declared`.

    Matching deliberately does NOT run here: the API call stays fast and
    the heavy fan-out happens in the consumer, which also lets any other
    producer (e.g. logistics) declare disasters through the same event.
    """
    # validates broadcast_type/source/targets combination up front
    resolved = resolve_broadcast_districts(
        broadcast_type=data.broadcast_type.value,
        source_district=data.source_district,
        target_districts=data.target_districts,
    )

    event = DisasterEvent(
        tenant_id=tenant_id,
        created_by=created_by,
        title=data.title,
        description=data.description,
        source_district=data.source_district,
        broadcast_type=data.broadcast_type,
        target_districts=data.target_districts or [],
        requirements=[
            EventRequirement(skill=r.skill, required_count=r.required_count)
            for r in data.requirements
        ],
    )
    db.add(event)
    db.flush()

    emit(
        db,
        routing_key="volunteer.disaster.declared",
        tenant_id=tenant_id,
        data={
            "event_id": str(event.id),
            "tenant_id": str(tenant_id),
            "title": event.title,
            "source_district": event.source_district,
            "broadcast_type": event.broadcast_type.value,
            "resolved_districts": resolved,
            "requirements": [
                {"skill": r.skill, "required_count": r.required_count}
                for r in event.requirements
            ],
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    db.commit()
    db.refresh(event)
    return event


# ---------------------------------------------------------------- matching


def _find_candidates(
    db: Session, *, districts: list[str], skill: str, exclude_volunteers: set[uuid.UUID]
) -> list[VolunteerProfile]:
    """The skill-bucket filter, as one plain SQL query:

        available AND active AND district IN (resolved) AND has skill

    JSONB containment (skills @> '["boat_driver"]') rides the GIN index."""
    stmt = (
        select(VolunteerProfile)
        .where(
            VolunteerProfile.available_status.is_(True),
            VolunteerProfile.is_active.is_(True),
            VolunteerProfile.base_district.in_(districts),
            VolunteerProfile.skills.contains([skill]),
        )
        .order_by(VolunteerProfile.created_at)  # deterministic notify order
    )
    return [v for v in db.scalars(stmt) if v.id not in exclude_volunteers]


def run_matching(db: Session, event_id: uuid.UUID) -> int:
    """Resolve districts, fill notification lists per skill bucket, emit
    one `volunteer.assignment.notified` per volunteer. Returns the number
    of volunteers notified. Idempotent per (event, volunteer): re-running
    can only add volunteers who were not yet mapped."""
    event = db.scalars(
        select(DisasterEvent)
        .where(DisasterEvent.id == event_id)
        .options(selectinload(DisasterEvent.requirements))
        .with_for_update()
    ).first()
    if event is None:
        log.warning("matching skipped: unknown event %s", event_id)
        return 0
    if event.status not in (EventStatus.DECLARED, EventStatus.BROADCASTING):
        log.info("matching skipped: event %s is %s", event_id, event.status.value)
        return 0

    districts = resolve_broadcast_districts(
        broadcast_type=event.broadcast_type.value,
        source_district=event.source_district,
        target_districts=event.target_districts,
    )

    already_mapped = {
        m.volunteer_id
        for m in db.scalars(
            select(EventVolunteerMapping).where(EventVolunteerMapping.event_id == event.id)
        )
    }

    notified = 0
    for requirement in event.requirements:
        if requirement.status is not RequirementStatus.OPEN:
            continue
        for volunteer in _find_candidates(
            db,
            districts=districts,
            skill=requirement.skill,
            exclude_volunteers=already_mapped,
        ):
            db.add(
                EventVolunteerMapping(
                    event_id=event.id,
                    requirement_id=requirement.id,
                    volunteer_id=volunteer.id,
                    status=AssignmentStatus.NOTIFIED,
                )
            )
            # one volunteer -> one bucket per event, greedily in
            # requirement order; they can decline and be re-matched later
            already_mapped.add(volunteer.id)
            # the simulated push notification (a notification-service or
            # the RTO websocket hub consumes this)
            emit(
                db,
                routing_key="volunteer.assignment.notified",
                tenant_id=event.tenant_id,
                data={
                    "event_id": str(event.id),
                    "requirement_id": str(requirement.id),
                    "volunteer_user_id": str(volunteer.user_id),
                    "skill": requirement.skill,
                    "source_district": event.source_district,
                    "title": event.title,
                },
            )
            notified += 1

    event.status = EventStatus.BROADCASTING
    db.commit()
    log.info("event %s: notified %d volunteers across %s", event.id, notified, districts)
    return notified


# ---------------------------------------------------------------- accept (FCFS)


def accept_assignment(
    db: Session, *, mapping_id: uuid.UUID, volunteer_user_id: uuid.UUID
) -> EventVolunteerMapping:
    """First-come-first-serve acceptance.

    Race safety without locks-in-application-code:
    1. The mapping flips NOTIFIED -> ACCEPTED with a guarded UPDATE, so a
       double-tap (or duplicate request) can't accept twice.
    2. The quota increments with `SET filled_count = filled_count + 1
       WHERE filled_count < required_count`. Postgres row-locks the
       requirement, so of N concurrent accepts exactly
       (required - filled) succeed; the rest match zero rows and are
       converted to REJECTED_FULL. That single statement IS the FCFS gate.
    """
    mapping = db.scalars(
        select(EventVolunteerMapping)
        .join(VolunteerProfile, VolunteerProfile.id == EventVolunteerMapping.volunteer_id)
        .where(
            EventVolunteerMapping.id == mapping_id,
            VolunteerProfile.user_id == volunteer_user_id,  # ownership check
        )
    ).first()
    if mapping is None:
        raise AssignmentError("Assignment not found")

    now = datetime.now(timezone.utc)

    # step 1: claim the mapping (guards double-accept)
    claimed = db.execute(
        update(EventVolunteerMapping)
        .where(
            EventVolunteerMapping.id == mapping.id,
            EventVolunteerMapping.status == AssignmentStatus.NOTIFIED,
        )
        .values(status=AssignmentStatus.ACCEPTED, responded_at=now)
    ).rowcount
    if claimed == 0:
        raise AssignmentError(f"Assignment already {mapping.status.value.lower()}")

    # step 2: the atomic quota gate
    row = db.execute(
        update(EventRequirement)
        .where(
            EventRequirement.id == mapping.requirement_id,
            EventRequirement.filled_count < EventRequirement.required_count,
        )
        .values(filled_count=EventRequirement.filled_count + 1)
        .returning(EventRequirement.filled_count, EventRequirement.required_count)
    ).first()

    if row is None:
        # bucket filled between notification and this accept
        db.execute(
            update(EventVolunteerMapping)
            .where(EventVolunteerMapping.id == mapping.id)
            .values(status=AssignmentStatus.REJECTED_FULL, responded_at=now)
        )
        db.commit()
        raise QuotaFullError("This skill quota is already filled")

    filled, required = row
    if filled >= required:
        _mark_requirement_fulfilled(db, mapping.requirement_id)

    db.commit()
    db.refresh(mapping)
    return mapping


def _mark_requirement_fulfilled(db: Session, requirement_id: uuid.UUID) -> None:
    """Close the bucket; if it was the last open one, the team is formed.

    The parent event row is locked first so two buckets fulfilling
    concurrently cannot both miss the 'all fulfilled' condition (or both
    emit team.formed)."""
    requirement = db.get(EventRequirement, requirement_id)
    event = db.scalars(
        select(DisasterEvent)
        .where(DisasterEvent.id == requirement.event_id)
        .with_for_update()
    ).one()

    requirement.status = RequirementStatus.FULFILLED
    emit(
        db,
        routing_key="volunteer.requirement.fulfilled",
        tenant_id=event.tenant_id,
        data={
            "event_id": str(event.id),
            "requirement_id": str(requirement.id),
            "skill": requirement.skill,
            "required_count": requirement.required_count,
        },
    )
    db.flush()

    open_left = db.scalar(
        select(func.count())
        .select_from(EventRequirement)
        .where(
            EventRequirement.event_id == event.id,
            EventRequirement.status != RequirementStatus.FULFILLED,
        )
    )
    if open_left == 0 and event.status is not EventStatus.TEAM_FORMED:
        event.status = EventStatus.TEAM_FORMED
        accepted = db.scalars(
            select(EventVolunteerMapping)
            .where(
                EventVolunteerMapping.event_id == event.id,
                EventVolunteerMapping.status == AssignmentStatus.ACCEPTED,
            )
            .options(selectinload(EventVolunteerMapping.volunteer))
        ).all()
        emit(
            db,
            routing_key="volunteer.team.formed",
            tenant_id=event.tenant_id,
            data={
                "event_id": str(event.id),
                "title": event.title,
                "source_district": event.source_district,
                "team": [
                    {
                        "volunteer_user_id": str(m.volunteer.user_id),
                        "full_name": m.volunteer.full_name,
                        "phone": m.volunteer.phone,
                        "skill": db.get(EventRequirement, m.requirement_id).skill,
                        "base_district": m.volunteer.base_district,
                    }
                    for m in accepted
                ],
            },
        )


# ---------------------------------------------------------------- other transitions


_TRANSITIONS: dict[AssignmentStatus, frozenset[AssignmentStatus]] = {
    AssignmentStatus.DECLINED: frozenset({AssignmentStatus.NOTIFIED}),
    AssignmentStatus.EN_ROUTE: frozenset({AssignmentStatus.ACCEPTED}),
    AssignmentStatus.COMPLETED: frozenset({AssignmentStatus.EN_ROUTE, AssignmentStatus.ACCEPTED}),
}


def transition_assignment(
    db: Session,
    *,
    mapping_id: uuid.UUID,
    volunteer_user_id: uuid.UUID,
    new_status: AssignmentStatus,
) -> EventVolunteerMapping:
    """Guarded status walk for the non-quota transitions
    (NOTIFIED->DECLINED, ACCEPTED->EN_ROUTE->COMPLETED)."""
    allowed_from = _TRANSITIONS.get(new_status)
    if allowed_from is None:
        raise AssignmentError(f"Cannot transition to {new_status.value} directly")

    mapping = db.scalars(
        select(EventVolunteerMapping)
        .join(VolunteerProfile, VolunteerProfile.id == EventVolunteerMapping.volunteer_id)
        .where(
            EventVolunteerMapping.id == mapping_id,
            VolunteerProfile.user_id == volunteer_user_id,
        )
    ).first()
    if mapping is None:
        raise AssignmentError("Assignment not found")

    changed = db.execute(
        update(EventVolunteerMapping)
        .where(
            EventVolunteerMapping.id == mapping.id,
            EventVolunteerMapping.status.in_(allowed_from),
        )
        .values(status=new_status, responded_at=datetime.now(timezone.utc))
    ).rowcount
    if changed == 0:
        raise AssignmentError(
            f"Cannot move assignment from {mapping.status.value} to {new_status.value}"
        )

    emit(
        db,
        routing_key=f"volunteer.assignment.{new_status.value.lower().replace('_', '-')}",
        tenant_id=mapping.event.tenant_id,
        data={
            "event_id": str(mapping.event_id),
            "requirement_id": str(mapping.requirement_id),
            "volunteer_user_id": str(volunteer_user_id),
            "status": new_status.value,
        },
    )
    db.commit()
    db.refresh(mapping)
    return mapping
