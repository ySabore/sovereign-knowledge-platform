from __future__ import annotations

import ast
import unittest
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _literal_assignment(module: ast.Module, name: str) -> str | tuple[str, ...] | None:
    for node in module.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            value = node.value
        elif isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            value = node.value
        else:
            continue

        if isinstance(value, ast.Constant) and (isinstance(value.value, str) or value.value is None):
            return value.value
        if isinstance(value, ast.Tuple):
            return tuple(item.value for item in value.elts if isinstance(item, ast.Constant) and isinstance(item.value, str))
        return None
    return None


class AlembicRevisionGraphTests(unittest.TestCase):
    def test_revision_ids_are_unique_and_down_revisions_exist(self) -> None:
        revisions_by_id: dict[str, Path] = {}
        down_revisions: dict[str, tuple[str, ...]] = {}
        for migration_path in sorted(MIGRATIONS_DIR.glob("*.py")):
            module = ast.parse(migration_path.read_text(encoding="utf-8"))
            revision = _literal_assignment(module, "revision")
            self.assertIsInstance(revision, str, f"{migration_path.name} must declare a string revision")
            assert isinstance(revision, str)
            self.assertNotIn(
                revision,
                revisions_by_id,
                f"{migration_path.name} duplicates revision {revision} from {revisions_by_id.get(revision, migration_path).name}",
            )
            revisions_by_id[revision] = migration_path

            down_revision = _literal_assignment(module, "down_revision")
            if down_revision is None:
                down_revisions[revision] = ()
            elif isinstance(down_revision, str):
                down_revisions[revision] = (down_revision,)
            else:
                down_revisions[revision] = down_revision

        for revision, parents in down_revisions.items():
            for parent in parents:
                self.assertIn(parent, revisions_by_id, f"{revision} references missing down_revision {parent}")


if __name__ == "__main__":
    unittest.main()
