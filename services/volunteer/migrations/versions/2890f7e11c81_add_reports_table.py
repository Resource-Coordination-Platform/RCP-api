"""Add reports table

Revision ID: 2890f7e11c81
Revises: b81d3d7f3ef1
Create Date: 2026-07-25 07:30:34.039900

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2890f7e11c81'
down_revision: Union[str, None] = 'b81d3d7f3ef1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'volunteer_reports',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('volunteer_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('schema_volunteer.volunteer_profiles.id'), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('district', sa.String(), nullable=False),
        sa.Column('city', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('image_url', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True, server_default='PENDING'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        schema='schema_volunteer'
    )

def downgrade() -> None:
    op.drop_table('volunteer_reports', schema='schema_volunteer')