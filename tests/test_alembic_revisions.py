from __future__ import annotations

import ast
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from app.config import settings

from alembic.config import Config
from alembic.script import ScriptDirectory


ROOT = Path(__file__).resolve().parents[1]
VERSIONS_DIR = ROOT / "alembic" / "versions"


def _literal_assignment(module: ast.Module, name: str) -> str | None:
    for node in module.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name) or node.target.id != name:
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return node.value.value
        if isinstance(node.value, ast.Constant) and node.value.value is None:
            return None
    raise AssertionError(f"{name} must be assigned as a literal in Alembic revisions")


class AlembicRevisionTests(unittest.TestCase):
    def test_revision_ids_are_unique(self) -> None:
        revisions: dict[str, Path] = {}
        for path in sorted(VERSIONS_DIR.glob("*.py")):
            module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            revision = _literal_assignment(module, "revision")
            self.assertIsNotNone(revision, f"{path.name} is missing revision")
            previous = revisions.get(str(revision))
            if previous is not None:
                self.fail(f"Duplicate Alembic revision {revision!r}: {previous.name} and {path.name}")
            revisions[str(revision)] = path

    def test_revision_graph_has_single_head(self) -> None:
        config = Config(str(ROOT / "alembic.ini"))
        script = ScriptDirectory.from_config(config)
        self.assertEqual(script.get_heads(), ["022"])

    def test_embedding_dimension_migration_refuses_to_retype_existing_vectors(self) -> None:
        path = VERSIONS_DIR / "021_embedding_dimensions_configurable.py"
        spec = importlib.util.spec_from_file_location("embedding_dimensions_configurable", path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        old_dimensions = settings.embedding_dimensions
        try:
            settings.embedding_dimensions = 384
            module._retype_embedding_column = Mock()
            module.op = SimpleNamespace(
                get_bind=lambda: SimpleNamespace(
                    execute=lambda _: SimpleNamespace(first=lambda: object()),
                )
            )

            with self.assertRaisesRegex(RuntimeError, "existing embeddings"):
                module.upgrade()

            module._retype_embedding_column.assert_not_called()
        finally:
            settings.embedding_dimensions = old_dimensions


if __name__ == "__main__":
    unittest.main()

