"""init_analytics

Revision ID: a1c3e5f70001
Revises:
Create Date: 2026-07-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1c3e5f70001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'analytics_categories',
        sa.Column('category_id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('unit', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('category_id'),
        schema='schema_analytics',
    )
    op.create_index(
        'ix_schema_analytics_analytics_categories_tenant_id',
        'analytics_categories',
        ['tenant_id'],
        unique=False,
        schema='schema_analytics',
    )

    op.create_table(
        'analytics_inventory_items',
        sa.Column('item_id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('category_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('quantity_total', sa.Integer(), nullable=False),
        sa.Column('quantity_reserved', sa.Integer(), nullable=False),
        sa.Column('quantity_available', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['category_id'], ['schema_analytics.analytics_categories.category_id']),
        sa.PrimaryKeyConstraint('item_id'),
        schema='schema_analytics',
    )
    op.create_index(
        'ix_schema_analytics_analytics_inventory_items_tenant_id',
        'analytics_inventory_items',
        ['tenant_id'],
        unique=False,
        schema='schema_analytics',
    )
    op.create_index(
        'ix_schema_analytics_analytics_inventory_items_category_id',
        'analytics_inventory_items',
        ['category_id'],
        unique=False,
        schema='schema_analytics',
    )

    op.create_table(
        'analytics_requests',
        sa.Column('request_id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('category_id', sa.UUID(), nullable=False),
        sa.Column('quantity_needed', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('urgency', sa.String(length=20), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('request_id'),
        schema='schema_analytics',
    )
    op.create_index(
        'ix_schema_analytics_analytics_requests_tenant_id',
        'analytics_requests',
        ['tenant_id'],
        unique=False,
        schema='schema_analytics',
    )
    op.create_index(
        'ix_schema_analytics_analytics_requests_category_id',
        'analytics_requests',
        ['category_id'],
        unique=False,
        schema='schema_analytics',
    )

    op.create_table(
        'processed_events',
        sa.Column('event_id', sa.UUID(), nullable=False),
        sa.Column('event_type', sa.String(length=200), nullable=False),
        sa.Column(
            'processed_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('event_id'),
        schema='schema_analytics',
    )


def downgrade() -> None:
    op.drop_table('analytics_requests', schema='schema_analytics')
    op.drop_table('analytics_inventory_items', schema='schema_analytics')
    op.drop_table('analytics_categories', schema='schema_analytics')
    op.drop_table('processed_events', schema='schema_analytics')
