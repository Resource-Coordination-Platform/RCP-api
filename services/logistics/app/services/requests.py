"""Help-request lifecycle. The steps are not fixed: each resource category
carries its own form definition and approval flow (the customizable workflow
engine), and both are enforced here — see app/services/form_schema.py and
app/services/workflow.py."""

import uuid
from datetime import datetime, timezone

from rcp_common.exceptions import ConflictError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import Principal
from app.events.publisher import emit
from app.models import HelpRequest, RequestStatus, ResourceCategory
from app.schemas.request_schema import HelpRequestCreate
from app.services import form_schema, workflow
from app.services.inventory import get_category


def create_request(db: Session, principal: Principal, data: HelpRequestCreate) -> HelpRequest:
    category = get_category(db, principal.tenant_id, data.category_id)
    if not category.is_active:
        raise ConflictError(f"Resource category '{category.name}' is no longer accepting requests")

    payload = data.model_dump()
    payload["extra_fields"] = form_schema.validate_payload(
        category.form_schema, payload.get("extra_fields")
    )

    request = HelpRequest(
        tenant_id=principal.tenant_id,
        requester_user_id=principal.user_id,
        status=workflow.initial_status(category.workflow),
        **payload,
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
            "status": request.status.value,
            "updated_at": request.created_at.isoformat() if request.created_at else None,
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
        select(HelpRequest)
        .where(HelpRequest.id == request_id, HelpRequest.tenant_id == tenant_id)
        .options(selectinload(HelpRequest.category))
    ).one_or_none()


def change_status(
    db: Session, request: HelpRequest, new_status: RequestStatus, principal: Principal
) -> HelpRequest:
    category: ResourceCategory | None = request.category
    allowed = workflow.allowed_next(category.workflow if category else None, request.status)
    if new_status not in allowed:
        options = sorted(status.value for status in allowed) or ["none — this state is final"]
        raise ValueError(
            f"Cannot move request from {request.status.value} to {new_status.value}; "
            f"this category allows: {', '.join(options)}"
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
            "category_id": str(request.category_id),
            "quantity_needed": request.quantity_needed,
            "status": new_status.value,
            "old_status": old_status.value,
            "new_status": new_status.value,
            "requester_user_id": (
                str(request.requester_user_id) if request.requester_user_id else None
            ),
            "changed_by_user_id": str(principal.user_id),
            "updated_at": now.isoformat(),
        },
    )
    db.commit()
    db.refresh(request)
    return request
