"""Reporting & Analytics service (ORM aggregation examples):
the "Need vs. Fulfillment" metrics for the coordinator dashboard."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import HelpRequest, InventoryItem, RequestStatus, ResourceCategory


def need_vs_fulfillment(db: Session, tenant_id: uuid.UUID) -> list[dict]:
    """Per category: open needs vs fulfilled requests vs stock on hand."""
    open_statuses = (
        RequestStatus.PENDING,
        RequestStatus.VERIFIED,
        RequestStatus.APPROVED,
        RequestStatus.IN_PROGRESS,
    )

    stmt = (
        select(
            ResourceCategory.name.label("category"),
            func.count(HelpRequest.id)
            .filter(HelpRequest.status.in_(open_statuses))
            .label("open_requests"),
            func.count(HelpRequest.id)
            .filter(HelpRequest.status == RequestStatus.FULFILLED)
            .label("fulfilled_requests"),
            func.coalesce(
                func.sum(HelpRequest.quantity_needed).filter(
                    HelpRequest.status.in_(open_statuses)
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

    stock_stmt = (
        select(
            InventoryItem.category_id,
            func.coalesce(
                func.sum(InventoryItem.quantity_total - InventoryItem.quantity_reserved), 0
            ).label("stock"),
        )
        .where(InventoryItem.tenant_id == tenant_id)
        .group_by(InventoryItem.category_id)
    )
    stock_by_category = dict(db.execute(stock_stmt).all())

    category_ids = dict(
        db.execute(
            select(ResourceCategory.name, ResourceCategory.id).where(
                ResourceCategory.tenant_id == tenant_id
            )
        ).all()
    )

    return [
        {
            "category": row.category,
            "open_requests": row.open_requests,
            "fulfilled_requests": row.fulfilled_requests,
            "quantity_needed": int(row.quantity_needed),
            "stock_available": int(stock_by_category.get(category_ids.get(row.category), 0)),
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
