from __future__ import annotations

import ast
import unittest
from pathlib import Path


VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _literal_assignment(module: ast.Module, name: str) -> str | None:
    for stmt in module.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id == name:
            value = stmt.value
        elif isinstance(stmt, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in stmt.targets):
            value = stmt.value
        else:
            continue

        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
        if isinstance(value, ast.Constant) and value.value is None:
            return None
    raise AssertionError(f"{name} assignment must be a string literal or None")


class AlembicRevisionTests(unittest.TestCase):
    def test_revisions_are_unique_and_linear(self) -> None:
        revisions: dict[str, Path] = {}
        down_revisions: dict[str, str | None] = {}

        for path in sorted(VERSIONS_DIR.glob("*.py")):
            module = ast.parse(path.read_text(), filename=str(path))
            revision = _literal_assignment(module, "revision")
            down_revision = _literal_assignment(module, "down_revision")
            self.assertIsNotNone(revision, f"{path.name} must define revision")
            assert revision is not None
            self.assertNotIn(
                revision,
                revisions,
                f"Duplicate Alembic revision {revision!r}: {revisions.get(revision)} and {path}",
            )
            revisions[revision] = path
            down_revisions[revision] = down_revision

        for revision, down_revision in down_revisions.items():
            if down_revision is not None:
                self.assertIn(down_revision, revisions, f"{revision} points to missing down_revision {down_revision}")

        heads = sorted(set(revisions) - {down for down in down_revisions.values() if down is not None})
        self.assertEqual(["022"], heads)


if __name__ == "__main__":
    unittest.main()

