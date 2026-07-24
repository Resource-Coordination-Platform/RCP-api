"""user_replicas: allow global (tenant-less) actors

Volunteers, victims and donators register through the mobile path with
tenant_id NULL. The NOT NULL constraint here meant their iam.user.*
events could never be replicated, so dispatch had no way to resolve a
volunteer's name — and the admin portal had no volunteers to search.

Revision ID: c3f8a1b6d742
Revises: b7c1d4e9a250
Create Date: 2026-07-23 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'c3f8a1b6d742'
down_revision: Union[str, None] = 'b7c1d4e9a250'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'user_replicas',
        'tenant_id',
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
        schema='schema_logistics',
    )


def downgrade() -> None:
    # Global replicas cannot be expressed under the old constraint; drop
    # them so the column can go back to NOT NULL.
    op.execute('DELETE FROM schema_logistics.user_replicas WHERE tenant_id IS NULL')
    op.alter_column(
        'user_replicas',
        'tenant_id',
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
        schema='schema_logistics',
    )
