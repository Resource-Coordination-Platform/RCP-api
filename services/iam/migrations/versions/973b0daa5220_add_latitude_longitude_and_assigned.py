"""add latitude longitude and assigned_tenant

Revision ID: 973b0daa5220
Revises: b7f3c2a1d9e0
Create Date: 2026-08-02 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '973b0daa5220'
down_revision: Union[str, None] = 'b7f3c2a1d9e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # අලුත් Columns 3 එකතු කරනවා
    op.add_column('users', sa.Column('latitude', sa.Float(), nullable=True), schema='schema_iam')
    op.add_column('users', sa.Column('longitude', sa.Float(), nullable=True), schema='schema_iam')
    op.add_column('users', sa.Column('assigned_tenant_id', sa.UUID(), nullable=True), schema='schema_iam')


def downgrade() -> None:
    # Downgrade කරොත් Columns 3 මකලා දානවා
    op.drop_column('users', 'assigned_tenant_id', schema='schema_iam')
    op.drop_column('users', 'longitude', schema='schema_iam')
    op.drop_column('users', 'latitude', schema='schema_iam')