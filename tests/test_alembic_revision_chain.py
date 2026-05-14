from __future__ import annotations

import ast
import unittest
from pathlib import Path


VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _literal_assignment(tree: ast.Module, name: str) -> object:
    for node in tree.body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target = node.target
            value = node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target = node.targets[0]
            value = node.value
        if isinstance(target, ast.Name) and target.id == name and value is not None:
            return ast.literal_eval(value)
    raise AssertionError(f"{name} assignment not found")


def _as_revision_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [item for item in value if isinstance(item, str)]
    raise AssertionError(f"Unsupported down_revision value: {value!r}")


class AlembicRevisionChainTests(unittest.TestCase):
    def test_revisions_are_unique_and_form_single_chain(self) -> None:
        revisions_by_file: dict[str, str] = {}
        down_revisions: dict[str, list[str]] = {}

        for path in sorted(VERSIONS_DIR.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            revision = _literal_assignment(tree, "revision")
            self.assertIsInstance(revision, str, path.name)
            down_revision = _literal_assignment(tree, "down_revision")
            revisions_by_file[path.name] = revision
            down_revisions[revision] = _as_revision_list(down_revision)

        seen: dict[str, str] = {}
        duplicates: dict[str, list[str]] = {}
        for filename, revision in revisions_by_file.items():
            if revision in seen:
                duplicates.setdefault(revision, [seen[revision]]).append(filename)
            else:
                seen[revision] = filename
        self.assertEqual({}, duplicates)

        revisions = set(revisions_by_file.values())
        for revision, parents in down_revisions.items():
            for parent in parents:
                self.assertIn(parent, revisions, f"{revision} references missing parent {parent}")

        parent_revisions = {parent for parents in down_revisions.values() for parent in parents}
        heads = revisions - parent_revisions
        self.assertEqual({"022"}, heads)


if __name__ == "__main__":
    unittest.main()
