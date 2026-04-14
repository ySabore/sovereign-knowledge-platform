"""
Delete all organizations except the one matching KEEP_ORGANIZATION_SLUG (destructive).

Child rows cascade on FK (workspaces, memberships, etc.). Requires explicit opt-in:

  PRUNE_ORGANIZATIONS=true KEEP_ORGANIZATION_SLUG=sterling-vale-llp python scripts/prune_organizations_keep_slug.py

Resolves the kept org by KEEP_ORGANIZATION_SLUG (default sterling-vale-llp), or if none
matches, by KEEP_ORGANIZATION_NAME (default "Sterling & Vale LLP"). Refuses to run if neither
matches (avoids wiping every org by mistake).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
except ImportError:
    pass

from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models import Organization


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in ("1", "true", "yes", "y", "on")


def main() -> None:
    if not _truthy(os.environ.get("PRUNE_ORGANIZATIONS")):
        print("Set PRUNE_ORGANIZATIONS=true to run this script.")
        return

    keep_slug = os.environ.get("KEEP_ORGANIZATION_SLUG", "sterling-vale-llp").strip().lower()
    keep_name = os.environ.get("KEEP_ORGANIZATION_NAME", "Sterling & Vale LLP").strip()
    db = SessionLocal()
    try:
        keep = db.execute(select(Organization).where(Organization.slug == keep_slug)).scalar_one_or_none()
        if keep is None and keep_name:
            keep = db.execute(select(Organization).where(Organization.name == keep_name)).scalar_one_or_none()
        if keep is None:
            print(
                f"No organization with slug {keep_slug!r}"
                + (f" or name {keep_name!r}" if keep_name else "")
                + "; refusing to delete all organizations."
            )
            sys.exit(1)

        others = db.scalars(select(Organization).where(Organization.id != keep.id)).all()
        if not others:
            print(f"Only kept organization exists; nothing to prune.")
            return

        for org in others:
            print(f"Deleting organization {org.name!r} ({org.slug}) …")
        # Bulk DELETE lets PostgreSQL apply ON DELETE CASCADE. ORM session.delete() can try to
        # null FKs on memberships before flush, which violates NOT NULL on organization_id.
        res = db.execute(delete(Organization).where(Organization.id != keep.id))
        db.commit()
        n = res.rowcount if res.rowcount is not None and res.rowcount >= 0 else len(others)
        print(f"Done. Kept {keep.name!r} ({keep.slug}). Removed {n} organization(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
