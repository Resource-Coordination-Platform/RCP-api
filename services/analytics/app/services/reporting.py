"""'Need vs. Fulfillment' read-model queries for the admin dashboard.

Analytics owns no transactional data. It reads the logistics schema through
a SELECT-only database role (svc_analytics) — a read model, never a write
path. Queries are plain SQL so this service carries no copy of the
logistics ORM models.

NOTE: SQLAlchemy enum columns store the *names* of the Python enum members
(e.g. 'PENDING', 'IN_PROGRESS'); the API contract exposes the *values*
('pending', 'in_progress'), which for these enums is exactly lower(name).
"""

import uuid

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.core.config import settings

_SCHEMA = settings.LOGISTICS_SCHEMA

_OPEN_STATUSES = ["PENDING", "VERIFIED", "APPROVED", "IN_PROGRESS"]

_NEED_VS_FULFILLMENT_SQL = text(
    f"""
    SELECT
        c.id AS category_id,
        c.name AS category,
        COUNT(r.id) FILTER (WHERE r.status::text IN :open_statuses) AS open_requests,
        COUNT(r.id) FILTER (WHERE r.status::text = 'FULFILLED') AS fulfilled_requests,
        COALESCE(
            SUM(r.quantity_needed) FILTER (WHERE r.status::text IN :open_statuses), 0
        ) AS quantity_needed
    FROM {_SCHEMA}.resource_categories c
    LEFT JOIN {_SCHEMA}.help_requests r ON r.category_id = c.id
    WHERE c.tenant_id = :tenant_id
    GROUP BY c.id, c.name
    ORDER BY c.name
    """
).bindparams(bindparam("open_statuses", expanding=True))

_STOCK_SQL = text(
    f"""
    SELECT
        i.category_id,
        COALESCE(SUM(i.quantity_total - i.quantity_reserved), 0) AS stock_available
    FROM {_SCHEMA}.inventory_items i
    WHERE i.tenant_id = :tenant_id
    GROUP BY i.category_id
    """
)

_STATUS_SUMMARY_SQL = text(
    f"""
    SELECT lower(r.status::text) AS status, COUNT(r.id) AS total
    FROM {_SCHEMA}.help_requests r
    WHERE r.tenant_id = :tenant_id
    GROUP BY r.status
    """
)


def need_vs_fulfillment(db: Session, tenant_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        _NEED_VS_FULFILLMENT_SQL,
        {"tenant_id": tenant_id, "open_statuses": _OPEN_STATUSES},
    ).all()

    stock_by_category = {
        row.category_id: int(row.stock_available)
        for row in db.execute(_STOCK_SQL, {"tenant_id": tenant_id}).all()
    }

    return [
        {
            "category_id": str(row.category_id),
            "category": row.category,
            "open_requests": row.open_requests,
            "fulfilled_requests": row.fulfilled_requests,
            "quantity_needed": int(row.quantity_needed),
            "stock_available": stock_by_category.get(row.category_id, 0),
        }
        for row in rows
    ]


def request_status_summary(db: Session, tenant_id: uuid.UUID) -> dict[str, int]:
    rows = db.execute(_STATUS_SUMMARY_SQL, {"tenant_id": tenant_id}).all()
    return {row.status: row.total for row in rows}
