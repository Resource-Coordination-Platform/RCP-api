"""'Need vs. Fulfillment' read-model queries for the admin dashboard.

Analytics now owns its own projection tables in schema_analytics and is
fed by logistics events over RabbitMQ. The service no longer queries the
logistics database directly.
"""

import uuid

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.core.config import settings

_SCHEMA = "schema_analytics"

_OPEN_STATUSES = ["pending", "verified", "approved", "in_progress"]

_NEED_VS_FULFILLMENT_SQL = text(
    f"""
    SELECT
        c.category_id AS category_id,
        c.name AS category,
        COUNT(r.request_id) FILTER (WHERE r.status IN :open_statuses) AS open_requests,
        COUNT(r.request_id) FILTER (WHERE r.status = 'fulfilled') AS fulfilled_requests,
        COALESCE(
            SUM(r.quantity_needed) FILTER (WHERE r.status IN :open_statuses), 0
        ) AS quantity_needed
    FROM {_SCHEMA}.analytics_categories c
    LEFT JOIN {_SCHEMA}.analytics_requests r ON r.category_id = c.category_id
    WHERE c.tenant_id = :tenant_id
    GROUP BY c.category_id, c.name
    ORDER BY c.name
    """
).bindparams(bindparam("open_statuses", expanding=True))

_STOCK_SQL = text(
    f"""
    SELECT
        i.category_id,
        COALESCE(SUM(i.quantity_total - i.quantity_reserved), 0) AS stock_available
    FROM {_SCHEMA}.analytics_inventory_items i
    WHERE i.tenant_id = :tenant_id
    GROUP BY i.category_id
    """
)

_STATUS_SUMMARY_SQL = text(
    f"""
    SELECT r.status AS status, COUNT(r.request_id) AS total
    FROM {_SCHEMA}.analytics_requests r
    WHERE r.tenant_id = :tenant_id
    GROUP BY r.status
    """
)


def need_vs_fulfillment(db: Session, tenant_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        _NEED_VS_FULFILLMENT_SQL,
        {"tenant_id": tenant_id.hex, "open_statuses": _OPEN_STATUSES},
    ).all()

    stock_by_category = {
        row.category_id: int(row.stock_available)
        for row in db.execute(_STOCK_SQL, {"tenant_id": tenant_id.hex}).all()
    }

    return [
        {
            "category_id": str(uuid.UUID(row.category_id)) if isinstance(row.category_id, str) and len(row.category_id) == 32 else str(row.category_id),
            "category": row.category,
            "open_requests": row.open_requests,
            "fulfilled_requests": row.fulfilled_requests,
            "quantity_needed": int(row.quantity_needed),
            "stock_available": stock_by_category.get(row.category_id, 0),
        }
        for row in rows
    ]


def request_status_summary(db: Session, tenant_id: uuid.UUID) -> dict[str, int]:
    rows = db.execute(_STATUS_SUMMARY_SQL, {"tenant_id": tenant_id.hex}).all()
    return {row.status: row.total for row in rows}
