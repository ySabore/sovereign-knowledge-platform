from __future__ import annotations

import ast
from pathlib import Path
import unittest


VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _literal_assignment(module: ast.Module, name: str) -> object:
    for node in module.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing {name!r} assignment")


class AlembicRevisionGraphTests(unittest.TestCase):
    def test_revision_ids_are_unique_and_have_single_head(self) -> None:
        revisions: dict[str, str] = {}
        down_revisions: set[str] = set()

        for path in VERSIONS_DIR.glob("*.py"):
            module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            revision = _literal_assignment(module, "revision")
            down_revision = _literal_assignment(module, "down_revision")

            self.assertIsInstance(revision, str, path.name)
            self.assertNotIn(revision, revisions, f"{revision} is duplicated by {path.name} and {revisions.get(revision)}")
            revisions[revision] = path.name

            if isinstance(down_revision, str):
                down_revisions.add(down_revision)
            elif isinstance(down_revision, tuple):
                down_revisions.update(item for item in down_revision if item is not None)
            else:
                self.assertIsNone(down_revision, path.name)

        heads = sorted(set(revisions) - down_revisions)
        self.assertEqual(len(heads), 1, f"Expected one Alembic head, found {heads}")


if __name__ == "__main__":
    unittest.main()
