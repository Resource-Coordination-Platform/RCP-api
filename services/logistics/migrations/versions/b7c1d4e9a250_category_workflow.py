"""category workflow definition

Adds the per-category approval flow to resource_categories. NULL keeps the
platform default transitions, so existing categories are unaffected.

Revision ID: b7c1d4e9a250
Revises: ef9ee4c70bd9
Create Date: 2026-07-23 10:12:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b7c1d4e9a250'
down_revision: Union[str, None] = 'ef9ee4c70bd9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'resource_categories',
        sa.Column('workflow', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema='schema_logistics',
    )


def downgrade() -> None:
    op.drop_column('resource_categories', 'workflow', schema='schema_logistics')
