from __future__ import annotations

import ast
from pathlib import Path
import unittest


REVISION_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _literal_assignment(module: ast.Module, name: str) -> str | None:
    for node in module.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    return None


class AlembicRevisionGraphTests(unittest.TestCase):
    def test_revision_ids_are_unique_and_graph_has_single_head(self) -> None:
        revisions: dict[str, str] = {}
        down_revisions: dict[str, str | None] = {}

        for path in REVISION_DIR.glob("*.py"):
            module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            revision = _literal_assignment(module, "revision")
            down_revision = _literal_assignment(module, "down_revision")

            self.assertIsInstance(revision, str, f"{path.name} must declare a string revision")
            self.assertNotIn(revision, revisions, f"Duplicate Alembic revision {revision!r} in {path.name}")
            revisions[revision] = path.name
            down_revisions[revision] = down_revision

        referenced = {down for down in down_revisions.values() if down is not None}
        heads = set(revisions) - referenced

        self.assertEqual(heads, {"022"})


if __name__ == "__main__":
    unittest.main()
