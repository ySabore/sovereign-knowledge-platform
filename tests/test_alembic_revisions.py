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


def _down_revisions(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, (tuple, list)):
        return {revision for revision in value if isinstance(revision, str)}
    raise AssertionError(f"Unsupported down_revision value: {value!r}")


def _migration_graph() -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    seen_files: dict[str, str] = {}
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        revision = _literal_assignment(module, "revision")
        if not isinstance(revision, str):
            raise AssertionError(f"{path.name} has non-string revision {revision!r}")
        if revision in graph:
            raise AssertionError(
                f"Duplicate Alembic revision {revision!r}: {seen_files[revision]} and {path.name}"
            )
        seen_files[revision] = path.name
        graph[revision] = _down_revisions(_literal_assignment(module, "down_revision"))
    return graph


class AlembicRevisionTests(unittest.TestCase):
    def test_revisions_are_unique_and_linear(self) -> None:
        graph = _migration_graph()

        missing_parents = {
            revision: sorted(parents - graph.keys())
            for revision, parents in graph.items()
            if parents - graph.keys()
        }
        self.assertEqual(missing_parents, {})

        children_by_parent: dict[str, set[str]] = {}
        for revision, parents in graph.items():
            for parent in parents:
                children_by_parent.setdefault(parent, set()).add(revision)

        heads = set(graph) - set(children_by_parent)
        self.assertEqual(heads, {"022"})


if __name__ == "__main__":
    unittest.main()
