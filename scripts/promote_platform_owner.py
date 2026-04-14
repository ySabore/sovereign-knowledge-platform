"""Grant platform owner to an existing user by email (e.g. after first Clerk sign-in)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
except ImportError:
    pass

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User


def main() -> None:
    email = os.environ.get("PROMOTE_PLATFORM_OWNER_EMAIL", "").lower().strip()
    if not email:
        print(
            "Set PROMOTE_PLATFORM_OWNER_EMAIL=user@example.com then run this script.",
            file=sys.stderr,
        )
        sys.exit(1)

    db = SessionLocal()
    try:
        u = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if u is None:
            print(f"No user with email {email!r}. Sign in once with Clerk so the user row exists.", file=sys.stderr)
            sys.exit(1)
        if u.is_platform_owner:
            print(f"Already platform owner: {email}")
            return
        u.is_platform_owner = True
        db.commit()
        print(f"Granted platform owner: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
