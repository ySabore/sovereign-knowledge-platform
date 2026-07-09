from __future__ import annotations

import ast
import unittest
from pathlib import Path


def _literal_assignment(module: ast.Module, name: str) -> object:
    for node in module.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                return ast.literal_eval(node.value)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return ast.literal_eval(node.value)
    raise AssertionError(f"Missing Alembic assignment: {name}")


def _down_revision_values(raw: object) -> set[str]:
    if raw is None:
        return set()
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, (tuple, list)):
        return {value for value in raw if isinstance(value, str)}
    raise AssertionError(f"Unsupported down_revision value: {raw!r}")


class AlembicRevisionGraphTests(unittest.TestCase):
    def test_revision_ids_are_unique_and_linear(self) -> None:
        versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        revisions: dict[str, Path] = {}
        down_revisions: set[str] = set()

        for path in sorted(versions_dir.glob("*.py")):
            module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            revision = _literal_assignment(module, "revision")
            self.assertIsInstance(revision, str)
            if revision in revisions:
                self.fail(f"Duplicate Alembic revision {revision!r}: {revisions[revision].name} and {path.name}")
            revisions[revision] = path
            down_revisions.update(_down_revision_values(_literal_assignment(module, "down_revision")))

        missing_parents = down_revisions - set(revisions)
        self.assertFalse(missing_parents, f"Alembic down_revision references missing revisions: {sorted(missing_parents)}")

        heads = set(revisions) - down_revisions
        self.assertEqual(len(heads), 1, f"Expected one Alembic head, found {sorted(heads)}")


if __name__ == "__main__":
    unittest.main()
