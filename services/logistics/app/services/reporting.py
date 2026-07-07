"""'Need vs. Fulfillment' read-models for the admin dashboard."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import HelpRequest, InventoryItem, RequestStatus, ResourceCategory

_OPEN_STATUSES = (
    RequestStatus.PENDING,
    RequestStatus.VERIFIED,
    RequestStatus.APPROVED,
    RequestStatus.IN_PROGRESS,
)


def need_vs_fulfillment(db: Session, tenant_id: uuid.UUID) -> list[dict]:
    stmt = (
        select(
            ResourceCategory.id,
            ResourceCategory.name,
            func.count(HelpRequest.id)
            .filter(HelpRequest.status.in_(_OPEN_STATUSES))
            .label("open_requests"),
            func.count(HelpRequest.id)
            .filter(HelpRequest.status == RequestStatus.FULFILLED)
            .label("fulfilled_requests"),
            func.coalesce(
                func.sum(HelpRequest.quantity_needed).filter(
                    HelpRequest.status.in_(_OPEN_STATUSES)
                ),
                0,
            ).label("quantity_needed"),
        )
        .join(HelpRequest, HelpRequest.category_id == ResourceCategory.id, isouter=True)
        .where(ResourceCategory.tenant_id == tenant_id)
        .group_by(ResourceCategory.id, ResourceCategory.name)
        .order_by(ResourceCategory.name)
    )
    rows = db.execute(stmt).all()

    stock_by_category = dict(
        db.execute(
            select(
                InventoryItem.category_id,
                func.coalesce(
                    func.sum(InventoryItem.quantity_total - InventoryItem.quantity_reserved),
                    0,
                ),
            )
            .where(InventoryItem.tenant_id == tenant_id)
            .group_by(InventoryItem.category_id)
        ).all()
    )

    return [
        {
            "category_id": str(row.id),
            "category": row.name,
            "open_requests": row.open_requests,
            "fulfilled_requests": row.fulfilled_requests,
            "quantity_needed": int(row.quantity_needed),
            "stock_available": int(stock_by_category.get(row.id, 0)),
        }
        for row in rows
    ]


def request_status_summary(db: Session, tenant_id: uuid.UUID) -> dict[str, int]:
    stmt = (
        select(HelpRequest.status, func.count(HelpRequest.id))
        .where(HelpRequest.tenant_id == tenant_id)
        .group_by(HelpRequest.status)
    )
    return {status.value: count for status, count in db.execute(stmt).all()}
