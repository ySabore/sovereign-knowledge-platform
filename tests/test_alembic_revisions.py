from __future__ import annotations

import ast
import unittest
from pathlib import Path


VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _literal_assignment(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing Alembic assignment {name!r}")


def _down_revisions(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value if v is not None]


class AlembicRevisionGraphTests(unittest.TestCase):
    def test_revision_ids_are_unique_and_linear(self) -> None:
        revisions: dict[str, Path] = {}
        down_revisions: set[str] = set()
        for path in VERSIONS_DIR.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            revision = str(_literal_assignment(tree, "revision"))
            self.assertNotIn(
                revision,
                revisions,
                f"Duplicate Alembic revision {revision!r}: {path.name} and {revisions.get(revision, path).name}",
            )
            revisions[revision] = path
            down_revisions.update(_down_revisions(_literal_assignment(tree, "down_revision")))

        missing = down_revisions - set(revisions)
        self.assertEqual(missing, set())

        heads = set(revisions) - down_revisions
        self.assertEqual(len(heads), 1, f"Expected one Alembic head, found {sorted(heads)}")


if __name__ == "__main__":
    unittest.main()
