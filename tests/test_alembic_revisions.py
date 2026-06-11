from __future__ import annotations

import re
from collections import Counter
from pathlib import Path


REVISION_RE = re.compile(r'^revision:\s*[^=]*=\s*["\']([^"\']+)["\']', re.MULTILINE)


def test_alembic_revision_ids_are_unique() -> None:
    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    revisions: list[tuple[str, Path]] = []

    for path in versions_dir.glob("*.py"):
        match = REVISION_RE.search(path.read_text(encoding="utf-8"))
        assert match is not None, f"{path.name} is missing revision"
        revisions.append((match.group(1), path))

    counts = Counter(revision for revision, _ in revisions)
    duplicates = {revision for revision, count in counts.items() if count > 1}

    assert duplicates == set()

