from __future__ import annotations

import ast
import unittest
from pathlib import Path


class AlembicRevisionTests(unittest.TestCase):
    def test_revision_ids_are_unique(self) -> None:
        revisions: dict[str, Path] = {}
        for migration in Path("alembic/versions").glob("*.py"):
            tree = ast.parse(migration.read_text(encoding="utf-8"))
            revision = None
            for node in tree.body:
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "revision":
                    if isinstance(node.value, ast.Constant):
                        revision = str(node.value.value)
                        break
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "revision" and isinstance(node.value, ast.Constant):
                            revision = str(node.value.value)
                            break
            self.assertIsNotNone(revision, f"{migration} has no revision")
            self.assertNotIn(revision, revisions, f"{migration} duplicates {revision} from {revisions.get(revision)}")
            revisions[revision] = migration


if __name__ == "__main__":
    unittest.main()
