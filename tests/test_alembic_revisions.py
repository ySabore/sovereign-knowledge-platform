from __future__ import annotations

import ast
import unittest
from pathlib import Path


class AlembicRevisionTests(unittest.TestCase):
    def test_revision_ids_are_unique(self) -> None:
        versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        seen: dict[str, Path] = {}

        for migration_path in versions_dir.glob("*.py"):
            tree = ast.parse(migration_path.read_text(encoding="utf-8"), filename=str(migration_path))
            revision = None
            for node in tree.body:
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "revision":
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        revision = node.value.value
                    break
                if isinstance(node, ast.Assign):
                    targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
                    if "revision" in targets and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        revision = node.value.value
                        break

            self.assertIsNotNone(revision, f"{migration_path.name} does not declare revision")
            previous = seen.setdefault(str(revision), migration_path)
            self.assertIs(
                previous,
                migration_path,
                f"Duplicate Alembic revision {revision!r}: {previous.name} and {migration_path.name}",
            )


if __name__ == "__main__":
    unittest.main()
