"""decouple_global_users

Actor decoupling: mobile-app users (VOLUNTEER/VICTIM/DONATOR) become a
global, tenant-less pool; web-portal users (TENANT_ADMIN/COORDINATOR)
stay tenant-bound. tenant_id becomes nullable, user_type is introduced,
and a CHECK constraint enforces the pairing.

Revision ID: a4c9d1e0b2f7
Revises: 91e8fdce8367
Create Date: 2026-07-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a4c9d1e0b2f7'
down_revision: Union[str, None] = '91e8fdce8367'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "schema_iam"

user_type = sa.Enum(
    "VOLUNTEER", "VICTIM", "DONATOR", "TENANT_ADMIN", "COORDINATOR",
    name="user_type",
    schema=SCHEMA,
)


def upgrade() -> None:
    user_type.create(op.get_bind(), checkfirst=True)

    # 1) add user_type nullable, backfill from the legacy role assignments,
    #    then tighten to NOT NULL
    op.add_column(
        "users",
        sa.Column("user_type", user_type, nullable=True),
        schema=SCHEMA,
    )
    op.execute(f"""
        UPDATE {SCHEMA}.users u SET user_type = CASE
            WHEN EXISTS (SELECT 1 FROM {SCHEMA}.role_assignments ra
                         WHERE ra.user_id = u.id AND ra.role = 'tenant_admin')
                THEN 'TENANT_ADMIN'::{SCHEMA}.user_type
            WHEN EXISTS (SELECT 1 FROM {SCHEMA}.role_assignments ra
                         WHERE ra.user_id = u.id AND ra.role = 'volunteer')
                THEN 'COORDINATOR'::{SCHEMA}.user_type  -- legacy tenant "volunteers"
                                                        -- stay tenant staff; true
                                                        -- volunteers re-register via
                                                        -- the mobile app
            ELSE 'COORDINATOR'::{SCHEMA}.user_type
        END
        WHERE u.user_type IS NULL
    """)
    op.alter_column("users", "user_type", nullable=False, schema=SCHEMA)
    op.create_index(
        op.f("ix_schema_iam_users_user_type"), "users", ["user_type"], schema=SCHEMA
    )

    # 2) tenant_id becomes nullable (NULL == global user)
    op.alter_column("users", "tenant_id", nullable=True, schema=SCHEMA)
    op.alter_column("role_assignments", "tenant_id", nullable=True, schema=SCHEMA)

    # 3) uniqueness for the global pool: (tenant_id, email) never collides on
    #    NULL tenant_id, so global emails need a partial unique index
    op.create_index(
        "uq_users_global_email",
        "users",
        ["email"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("tenant_id IS NULL"),
    )

    # 4) the decoupling invariant
    op.create_check_constraint(
        "ck_users_type_tenancy",
        "users",
        "(user_type IN ('TENANT_ADMIN', 'COORDINATOR')) = (tenant_id IS NOT NULL)",
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_type_tenancy", "users", schema=SCHEMA)
    op.drop_index("uq_users_global_email", "users", schema=SCHEMA)
    # global users cannot survive a NOT NULL tenant_id; remove them first
    op.execute(f"DELETE FROM {SCHEMA}.role_assignments WHERE tenant_id IS NULL")
    op.execute(f"DELETE FROM {SCHEMA}.users WHERE tenant_id IS NULL")
    op.alter_column("role_assignments", "tenant_id", nullable=False, schema=SCHEMA)
    op.alter_column("users", "tenant_id", nullable=False, schema=SCHEMA)
    op.drop_index(op.f("ix_schema_iam_users_user_type"), "users", schema=SCHEMA)
    op.drop_column("users", "user_type", schema=SCHEMA)
    user_type.drop(op.get_bind(), checkfirst=True)
