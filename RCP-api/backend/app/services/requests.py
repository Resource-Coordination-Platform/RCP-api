"""Request & Needs Management service logic (ORM examples):
the submit -> verify -> approve -> fulfil lifecycle."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import HelpRequest, RequestStatus, User
from app.schemas.request_schema import HelpRequestCreate


def create_request(
    db: Session,
    tenant_id: uuid.UUID,
    data: HelpRequestCreate,
    requester: User | None = None,
) -> HelpRequest:
    request = HelpRequest(
        tenant_id=tenant_id,
        requester_id=requester.id if requester else None,
        **data.model_dump(),
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def list_requests(
    db: Session,
    tenant_id: uuid.UUID,
    status: RequestStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[HelpRequest]:
    stmt = (
        select(HelpRequest)
        .where(HelpRequest.tenant_id == tenant_id)
        .options(selectinload(HelpRequest.category))
        .order_by(HelpRequest.urgency.desc(), HelpRequest.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    if status is not None:
        stmt = stmt.where(HelpRequest.status == status)
    return list(db.scalars(stmt))


def get_request(
    db: Session, tenant_id: uuid.UUID, request_id: uuid.UUID
) -> HelpRequest | None:
    stmt = select(HelpRequest).where(
        HelpRequest.id == request_id, HelpRequest.tenant_id == tenant_id
    )
    return db.scalars(stmt).one_or_none()


# legal transitions of the request lifecycle
_ALLOWED_TRANSITIONS: dict[RequestStatus, set[RequestStatus]] = {
    RequestStatus.PENDING: {RequestStatus.VERIFIED, RequestStatus.REJECTED, RequestStatus.CANCELLED},
    RequestStatus.VERIFIED: {RequestStatus.APPROVED, RequestStatus.REJECTED, RequestStatus.CANCELLED},
    RequestStatus.APPROVED: {RequestStatus.IN_PROGRESS, RequestStatus.CANCELLED},
    RequestStatus.IN_PROGRESS: {RequestStatus.FULFILLED, RequestStatus.CANCELLED},
}


def change_status(
    db: Session,
    request: HelpRequest,
    new_status: RequestStatus,
    actor: User,
) -> HelpRequest:
    allowed = _ALLOWED_TRANSITIONS.get(request.status, set())
    if new_status not in allowed:
        raise ValueError(
            f"Cannot move request from {request.status.value} to {new_status.value}"
        )

    request.status = new_status
    now = datetime.now(timezone.utc)
    if new_status == RequestStatus.VERIFIED:
        request.verified_by_id = actor.id
        request.verified_at = now
    elif new_status == RequestStatus.FULFILLED:
        request.fulfilled_at = now

    db.commit()
    db.refresh(request)
    return request
