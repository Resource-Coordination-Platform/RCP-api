"""add volunteer_profiles.source_updated_at

The IAM consumer guards replica upserts with the *source* (IAM) timestamp
instead of the local updated_at, which moves on every local profile edit.
Nullable: rows replicated before this column existed have no known source
timestamp — the consumer treats NULL as "always accept the update".

Revision ID: b81d3d7f3ef1
Revises: a70c2c6f2de0
Create Date: 2026-07-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b81d3d7f3ef1'
down_revision: Union[str, None] = 'a70c2c6f2de0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'volunteer_profiles',
        sa.Column('source_updated_at', sa.DateTime(timezone=True), nullable=True),
        schema='schema_volunteer',
    )


def downgrade() -> None:
    op.drop_column('volunteer_profiles', 'source_updated_at', schema='schema_volunteer')
