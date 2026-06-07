from __future__ import annotations

import ast
import unittest
from pathlib import Path


class AlembicRevisionTests(unittest.TestCase):
    def test_migration_revision_ids_are_unique(self) -> None:
        versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        seen: dict[str, Path] = {}
        duplicates: list[str] = []

        for migration in sorted(versions_dir.glob("*.py")):
            tree = ast.parse(migration.read_text(encoding="utf-8"))
            revision = None
            for node in tree.body:
                if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
                    continue
                if node.target.id == "revision" and isinstance(node.value, ast.Constant):
                    revision = str(node.value.value)
                    break
            self.assertIsNotNone(revision, f"{migration.name} does not declare revision")
            if revision in seen:
                duplicates.append(f"{revision}: {seen[revision].name}, {migration.name}")
            else:
                seen[revision] = migration

        self.assertEqual([], duplicates)


if __name__ == "__main__":
    unittest.main()
