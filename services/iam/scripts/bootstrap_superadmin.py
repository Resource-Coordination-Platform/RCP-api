"""Create the first platform super admin.

There is no bootstrap super admin by default and the /api/admin/super-admins
endpoint requires an existing super admin — so the very first operator has to
be seeded out-of-band. Run this once after the IAM schema is migrated.

Usage (from services/iam, with the IAM virtualenv active):

    python -m scripts.bootstrap_superadmin \
        --email ops@rcp.local --password "change-me-please" --name "Platform Ops"

Or rely on env vars / interactive prompts:

    SUPERADMIN_EMAIL=ops@rcp.local SUPERADMIN_PASSWORD=... \
        python -m scripts.bootstrap_superadmin

The password is never echoed; it is argon2-hashed before storage. Re-running
with an existing email is a no-op.
"""

import argparse
import getpass
import os
import sys

from pydantic import BaseModel, EmailStr, ValidationError
from sqlalchemy import select

from app.db.database import SessionLocal
from app.core.security import hash_password
from app.models import User, UserType


class _EmailCheck(BaseModel):
    """Same EmailStr rule the login endpoint enforces.

    Without this the script will happily seed an address that /api/auth/login
    later rejects with a 422 — notably reserved TLDs like ``.local``, which
    would leave an operator permanently unable to sign in.
    """

    email: EmailStr


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the first super admin.")
    parser.add_argument("--email", default=os.getenv("SUPERADMIN_EMAIL"))
    parser.add_argument("--password", default=os.getenv("SUPERADMIN_PASSWORD"))
    parser.add_argument(
        "--name", default=os.getenv("SUPERADMIN_NAME", "Platform Super Admin")
    )
    args = parser.parse_args()

    email = args.email or input("Super admin email: ").strip()
    password = args.password or getpass.getpass("Super admin password (min 10 chars): ")

    if not email:
        print("error: email is required", file=sys.stderr)
        return 2
    try:
        _EmailCheck(email=email)
    except ValidationError as exc:
        reason = exc.errors()[0]["msg"]
        print(f"error: '{email}' is not a usable address — {reason}", file=sys.stderr)
        print(
            "hint: reserved TLDs (.local, .test, .invalid, .localhost) are "
            "rejected at login; use a real domain such as example.com",
            file=sys.stderr,
        )
        return 2
    if len(password) < 10:
        print("error: password must be at least 10 characters", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        existing = db.scalars(
            select(User).where(User.tenant_id.is_(None), User.email == email)
        ).first()
        if existing is not None:
            if existing.user_type == UserType.SUPER_ADMIN:
                print(f"Super admin '{email}' already exists — nothing to do.")
                return 0
            print(
                f"error: a global user with email '{email}' already exists "
                f"(type {existing.user_type.value})",
                file=sys.stderr,
            )
            return 1

        user = User(
            tenant_id=None,
            user_type=UserType.SUPER_ADMIN,
            email=email,
            password_hash=hash_password(password),
            full_name=args.name,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Created super admin '{email}' (id={user.id}).")
        print("Log in at the super-admin console with this email and password.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
