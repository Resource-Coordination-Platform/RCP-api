"""Help-request lifecycle: submit -> verify -> approve -> fulfil."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import Principal
from app.events.publisher import emit
from app.models import HelpRequest, RequestStatus
from app.schemas.request_schema import HelpRequestCreate

_ALLOWED_TRANSITIONS: dict[RequestStatus, set[RequestStatus]] = {
    RequestStatus.PENDING: {RequestStatus.VERIFIED, RequestStatus.REJECTED, RequestStatus.CANCELLED},
    RequestStatus.VERIFIED: {RequestStatus.APPROVED, RequestStatus.REJECTED, RequestStatus.CANCELLED},
    RequestStatus.APPROVED: {RequestStatus.IN_PROGRESS, RequestStatus.CANCELLED},
    RequestStatus.IN_PROGRESS: {RequestStatus.FULFILLED, RequestStatus.CANCELLED},
}


def create_request(db: Session, principal: Principal, data: HelpRequestCreate) -> HelpRequest:
    request = HelpRequest(
        tenant_id=principal.tenant_id,
        requester_user_id=principal.user_id,
        **data.model_dump(),
    )
    db.add(request)
    db.flush()
    emit(
        db,
        routing_key="logistics.request.submitted",
        tenant_id=principal.tenant_id,
        data={
            "request_id": str(request.id),
            "category_id": str(request.category_id),
            "urgency": request.urgency.value,
            "quantity_needed": request.quantity_needed,
            "area": request.area,
        },
    )
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


def get_request(db: Session, tenant_id: uuid.UUID, request_id: uuid.UUID) -> HelpRequest | None:
    return db.scalars(
        select(HelpRequest).where(
            HelpRequest.id == request_id, HelpRequest.tenant_id == tenant_id
        )
    ).one_or_none()


def change_status(
    db: Session, request: HelpRequest, new_status: RequestStatus, principal: Principal
) -> HelpRequest:
    allowed = _ALLOWED_TRANSITIONS.get(request.status, set())
    if new_status not in allowed:
        raise ValueError(
            f"Cannot move request from {request.status.value} to {new_status.value}"
        )

    old_status = request.status
    request.status = new_status
    now = datetime.now(timezone.utc)
    if new_status == RequestStatus.VERIFIED:
        request.verified_by_user_id = principal.user_id
        request.verified_at = now
    elif new_status == RequestStatus.FULFILLED:
        request.fulfilled_at = now

    emit(
        db,
        routing_key="logistics.request.status-changed",
        tenant_id=request.tenant_id,
        data={
            "request_id": str(request.id),
            "old_status": old_status.value,
            "new_status": new_status.value,
            "requester_user_id": (
                str(request.requester_user_id) if request.requester_user_id else None
            ),
            "changed_by_user_id": str(principal.user_id),
        },
    )
    db.commit()
    db.refresh(request)
    return request
