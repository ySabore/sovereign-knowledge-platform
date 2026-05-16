from __future__ import annotations

import ast
import unittest
from pathlib import Path


class AlembicRevisionTests(unittest.TestCase):
    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"

    @staticmethod
    def _assigned_literal(tree: ast.Module, name: str):
        for node in tree.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
                return ast.literal_eval(node.value)
            if isinstance(node, ast.Assign):
                targets = [target for target in node.targets if isinstance(target, ast.Name) and target.id == name]
                if targets:
                    return ast.literal_eval(node.value)
        raise AssertionError(f"Missing Alembic {name!r} assignment")

    def _revision_graph(self) -> tuple[dict[str, Path], set[str]]:
        revisions: dict[str, Path] = {}
        down_revisions: set[str] = set()
        for path in sorted(self.versions_dir.glob("*.py")):
            tree = ast.parse(path.read_text(), filename=str(path))
            revision = self._assigned_literal(tree, "revision")
            self.assertIsInstance(revision, str, path.name)
            self.assertNotIn(revision, revisions, f"Duplicate Alembic revision {revision!r} in {path.name}")
            revisions[revision] = path

            down_revision = self._assigned_literal(tree, "down_revision")
            if isinstance(down_revision, str):
                down_revisions.add(down_revision)
            elif isinstance(down_revision, (tuple, list)):
                down_revisions.update(item for item in down_revision if isinstance(item, str))
            else:
                self.assertIsNone(down_revision, path.name)
        return revisions, down_revisions

    def test_revisions_are_unique_and_have_single_head(self) -> None:
        revisions, down_revisions = self._revision_graph()
        heads = set(revisions) - down_revisions
        self.assertEqual(heads, {"022"})


if __name__ == "__main__":
    unittest.main()
