"""
Write Sterling & Vale demo PDFs to docs/demo/organizations/<org>/workspaces/<workspace-slug>/.

Requires: pip install fpdf2 (same as API requirements)

Usage (repo root):
  python scripts/write_demo_pdf_assets_to_docs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts = Path(__file__).resolve().parent
sys.path.insert(0, str(_scripts))

from law_firm_demo_pdf_catalog import (  # noqa: E402
    DEMO_ORGANIZATION_SLUG,
    DEMO_PDFS,
    workspace_dir_slug,
    write_demo_pdf,
)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    base = repo_root / "docs" / "demo" / "organizations" / DEMO_ORGANIZATION_SLUG / "workspaces"
    base.mkdir(parents=True, exist_ok=True)
    for spec in DEMO_PDFS:
        slug = workspace_dir_slug(spec["workspace"])
        dest = base / slug / spec["filename"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        write_demo_pdf(dest=dest, doc_title=spec["title"], body=spec["body"])
        print(f"Wrote {dest.relative_to(repo_root)}")
    print(f"Done. {len(DEMO_PDFS)} PDFs under docs/demo/organizations/{DEMO_ORGANIZATION_SLUG}/workspaces/")


if __name__ == "__main__":
    main()
