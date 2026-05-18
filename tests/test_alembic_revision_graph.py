import ast
import unittest
from collections import defaultdict
from pathlib import Path
from typing import Any


VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _assignment_literal(module: ast.Module, name: str) -> Any:
    for node in module.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found")


def _revision_metadata() -> dict[str, tuple[Path, tuple[str, ...]]]:
    revisions: dict[str, tuple[Path, tuple[str, ...]]] = {}
    duplicates: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        module = ast.parse(path.read_text(), filename=str(path))
        revision = _assignment_literal(module, "revision")
        down_revision = _assignment_literal(module, "down_revision")
        parents = _normalize_down_revisions(down_revision)
        if revision in revisions:
            duplicates[revision].append(path)
        else:
            revisions[revision] = (path, parents)

    if duplicates:
        duplicate_report = {
            revision: [str(revisions[revision][0]), *[str(path) for path in paths]]
            for revision, paths in duplicates.items()
        }
        raise AssertionError(f"Duplicate Alembic revision ids: {duplicate_report}")
    return revisions


def _normalize_down_revisions(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(value)
    raise AssertionError(f"Unsupported down_revision value: {value!r}")


class AlembicRevisionGraphTest(unittest.TestCase):
    def test_revision_ids_are_unique(self) -> None:
        revisions = _revision_metadata()

        self.assertGreater(len(revisions), 0)

    def test_revision_graph_has_no_missing_parents_and_single_head(self) -> None:
        revisions = _revision_metadata()
        parent_revisions = {parent for _, parents in revisions.values() for parent in parents}
        missing_parents = sorted(parent for parent in parent_revisions if parent not in revisions)

        self.assertEqual([], missing_parents)
        heads = sorted(set(revisions) - parent_revisions)
        self.assertEqual(["022"], heads)


if __name__ == "__main__":
    unittest.main()
