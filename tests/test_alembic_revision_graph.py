from __future__ import annotations

import ast
import unittest
from pathlib import Path


VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _literal_assignment(tree: ast.Module, name: str):
    for node in tree.body:
        target = None
        value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
        if isinstance(target, ast.Name) and target.id == name and value is not None:
            return ast.literal_eval(value)
    raise AssertionError(f"Missing {name} assignment")


def _down_revisions(value) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    return {item for item in value if item is not None}


class AlembicRevisionGraphTests(unittest.TestCase):
    def test_revisions_are_unique_and_have_single_head(self) -> None:
        revisions: dict[str, Path] = {}
        down_revisions: set[str] = set()
        for path in sorted(VERSIONS_DIR.glob("*.py")):
            if path.name == "__init__.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            revision = _literal_assignment(tree, "revision")
            self.assertNotIn(revision, revisions, f"Duplicate Alembic revision {revision} in {path} and {revisions.get(revision)}")
            revisions[revision] = path
            down_revisions.update(_down_revisions(_literal_assignment(tree, "down_revision")))

        self.assertTrue(revisions)
        missing = down_revisions.difference(revisions)
        self.assertEqual(missing, set())
        heads = set(revisions).difference(down_revisions)
        self.assertEqual(heads, {"022"})


if __name__ == "__main__":
    unittest.main()
