"""add_super_admin

Introduce the SUPER_ADMIN platform operator. It is a tenant-less actor (like
the mobile pool) but distinct: it powers the super-admin console and is never
self-registerable. Only a new enum value is needed — the existing
ck_users_type_tenancy constraint already forces any non-(TENANT_ADMIN,
COORDINATOR) user to have a NULL tenant_id, so SUPER_ADMIN is global by
construction.

Revision ID: b7f3c2a1d9e0
Revises: a4c9d1e0b2f7
Create Date: 2026-07-23

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b7f3c2a1d9e0'
down_revision: Union[str, None] = 'a4c9d1e0b2f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "schema_iam"


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction on older
    # PostgreSQL; use alembic's autocommit block so this is portable.
    with op.get_context().autocommit_block():
        op.execute(
            f"ALTER TYPE {SCHEMA}.user_type ADD VALUE IF NOT EXISTS 'SUPER_ADMIN'"
        )


def downgrade() -> None:
    # PostgreSQL cannot drop a single value from an enum. Removing SUPER_ADMIN
    # would require rebuilding the type; downgrade is a no-op (any SUPER_ADMIN
    # rows must be deleted manually before the type could be rebuilt).
    pass
