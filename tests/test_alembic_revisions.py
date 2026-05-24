from __future__ import annotations

import ast
import unittest
from pathlib import Path
from typing import Any


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _literal_assignment(module: ast.Module, name: str) -> Any:
    for node in module.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Migration is missing {name!r}")


def _iter_down_revisions(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (tuple, list)):
        return [item for item in value if item is not None]
    raise AssertionError(f"Unsupported down_revision value: {value!r}")


class AlembicRevisionTests(unittest.TestCase):
    def test_migration_revisions_are_unique_and_resolvable(self) -> None:
        revisions: dict[str, Path] = {}
        down_revisions: list[tuple[str, Path]] = []

        for path in sorted(MIGRATIONS_DIR.glob("*.py")):
            module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            revision = _literal_assignment(module, "revision")
            self.assertIsInstance(revision, str)
            self.assertNotIn(revision, revisions, f"Duplicate Alembic revision {revision!r} in {path.name}")
            revisions[revision] = path
            down_revisions.extend((down_revision, path) for down_revision in _iter_down_revisions(_literal_assignment(module, "down_revision")))

        self.assertTrue(revisions, "Expected at least one Alembic revision")
        for down_revision, path in down_revisions:
            self.assertIn(down_revision, revisions, f"{path.name} points at missing down_revision {down_revision!r}")


if __name__ == "__main__":
    unittest.main()
