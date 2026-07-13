from __future__ import annotations

import ast
import unittest
from pathlib import Path


class AlembicRevisionGraphTests(unittest.TestCase):
    def test_revisions_are_unique_and_single_head(self) -> None:
        versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        revisions: dict[str, Path] = {}
        down_revisions: dict[str, list[str]] = {}

        for path in versions_dir.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            values: dict[str, object] = {}
            for node in tree.body:
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    name = node.target.id
                elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    name = node.targets[0].id
                else:
                    continue
                if name in {"revision", "down_revision"}:
                    values[name] = ast.literal_eval(node.value)

            revision = values.get("revision")
            self.assertIsInstance(revision, str, f"{path.name} must define a string revision")
            assert isinstance(revision, str)
            self.assertNotIn(revision, revisions, f"Duplicate Alembic revision {revision!r}: {path.name} and {revisions.get(revision)}")
            revisions[revision] = path

            raw_down = values.get("down_revision")
            if raw_down is None:
                down_revisions[revision] = []
            elif isinstance(raw_down, str):
                down_revisions[revision] = [raw_down]
            elif isinstance(raw_down, (tuple, list)):
                down_revisions[revision] = [str(item) for item in raw_down]
            else:
                self.fail(f"{path.name} has unsupported down_revision value {raw_down!r}")

        referenced = {down for downs in down_revisions.values() for down in downs}
        missing = sorted(referenced - set(revisions))
        self.assertEqual(missing, [], "Alembic down_revision values must refer to existing revisions")

        heads = sorted(set(revisions) - referenced)
        self.assertEqual(heads, ["022"], f"Expected a single Alembic head, got {heads}")


if __name__ == "__main__":
    unittest.main()
