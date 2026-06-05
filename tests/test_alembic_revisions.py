from __future__ import annotations

import ast
import unittest
from collections import defaultdict
from pathlib import Path


def _string_assignment(module: ast.Module, name: str) -> str | None:
    for node in module.body:
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
    return None


class AlembicRevisionTests(unittest.TestCase):
    def test_revision_ids_are_unique(self) -> None:
        revisions: dict[str, list[Path]] = defaultdict(list)
        versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        for migration in versions_dir.glob("*.py"):
            module = ast.parse(migration.read_text(), filename=str(migration))
            revision = _string_assignment(module, "revision")
            self.assertIsNotNone(revision, f"{migration.name} is missing a revision id")
            revisions[str(revision)].append(migration)

        duplicates = {revision: paths for revision, paths in revisions.items() if len(paths) > 1}
        self.assertEqual(
            duplicates,
            {},
            "Alembic revision IDs must be unique so migrations can build a valid revision map.",
        )


if __name__ == "__main__":
    unittest.main()
