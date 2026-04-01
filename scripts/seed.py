"""Create platform owner user for development. Run after migrations."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.auth.security import hash_password
from app.database import SessionLocal
from app.models import User


def main() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
    except ImportError:
        pass

    email = os.environ.get("SEED_PLATFORM_OWNER_EMAIL", "owner@example.com").lower().strip()
    password = os.environ.get("SEED_PLATFORM_OWNER_PASSWORD", "ChangeMeNow!")
    full_name = os.environ.get("SEED_PLATFORM_OWNER_NAME", "Platform Owner")

    db = SessionLocal()
    try:
        existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if existing:
            print(f"User already exists: {email}")
            return
        u = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            is_active=True,
            is_platform_owner=True,
        )
        db.add(u)
        db.commit()
        print(f"Seeded platform owner: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
