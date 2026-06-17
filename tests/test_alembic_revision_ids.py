from __future__ import annotations

import ast
import unittest
from pathlib import Path


class AlembicRevisionIdTests(unittest.TestCase):
    def test_revision_ids_are_unique(self) -> None:
        revisions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        seen: dict[str, Path] = {}

        for migration_path in sorted(revisions_dir.glob("*.py")):
            module = ast.parse(migration_path.read_text())
            revision = None
            for node in module.body:
                if not isinstance(node, ast.AnnAssign | ast.Assign):
                    continue
                target = node.target if isinstance(node, ast.AnnAssign) else node.targets[0]
                if isinstance(target, ast.Name) and target.id == "revision" and isinstance(node.value, ast.Constant):
                    revision = node.value.value
                    break
            self.assertIsInstance(revision, str, f"{migration_path.name} must declare a string revision")
            if revision in seen:
                self.fail(f"Duplicate Alembic revision {revision!r}: {seen[revision].name} and {migration_path.name}")
            seen[revision] = migration_path


if __name__ == "__main__":
    unittest.main()
