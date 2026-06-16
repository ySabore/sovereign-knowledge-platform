from __future__ import annotations

import ast
import unittest
from pathlib import Path


VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _literal_assignment(module: ast.Module, name: str) -> str | tuple[str, ...] | None:
    for node in module.body:
        target_name = None
        value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target_name = node.targets[0].id
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_name = node.target.id
            value = node.value
        if target_name == name and value is not None:
            return ast.literal_eval(value)
    return None


class AlembicRevisionTests(unittest.TestCase):
    def test_revisions_are_unique_and_linear(self) -> None:
        revisions: dict[str, str] = {}
        down_revisions: dict[str, tuple[str, ...]] = {}
        for path in VERSIONS_DIR.glob("*.py"):
            module = ast.parse(path.read_text())
            revision = _literal_assignment(module, "revision")
            self.assertIsInstance(revision, str, path.name)
            self.assertNotIn(revision, revisions, f"duplicate revision {revision!r} in {path} and {revisions.get(revision)}")
            revisions[revision] = path.name

            raw_down = _literal_assignment(module, "down_revision")
            if raw_down is None:
                down_revisions[revision] = ()
            elif isinstance(raw_down, str):
                down_revisions[revision] = (raw_down,)
            else:
                down_revisions[revision] = tuple(raw_down)

        referenced = {down for downs in down_revisions.values() for down in downs if down is not None}
        heads = set(revisions) - referenced
        self.assertEqual(heads, {"022"})

    def test_initial_embedding_migration_keeps_historical_dimension(self) -> None:
        contents = (VERSIONS_DIR / "002_ingestion_retrieval.py").read_text()
        self.assertIn("pgvector.sqlalchemy.Vector(768)", contents)
        self.assertNotIn("from app.config import settings", contents)


if __name__ == "__main__":
    unittest.main()
