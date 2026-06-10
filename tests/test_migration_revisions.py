from __future__ import annotations

import ast
from pathlib import Path
import unittest


MIGRATION_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _literal_assignment(module: ast.Module, name: str) -> object:
    for node in module.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"missing {name!r} assignment")


def _revision_graph() -> dict[str, str | tuple[str, ...] | None]:
    graph: dict[str, str | tuple[str, ...] | None] = {}
    for path in MIGRATION_DIR.glob("*.py"):
        if path.name == "__init__.py":
            continue
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        revision = _literal_assignment(module, "revision")
        down_revision = _literal_assignment(module, "down_revision")
        if not isinstance(revision, str):
            raise AssertionError(f"{path.name}: revision must be a string")
        if revision in graph:
            raise AssertionError(f"duplicate revision id {revision!r}")
        graph[revision] = down_revision
    return graph


class MigrationRevisionTests(unittest.TestCase):
    def test_revisions_are_unique(self) -> None:
        self.assertGreater(len(_revision_graph()), 0)

    def test_migration_graph_has_single_head(self) -> None:
        graph = _revision_graph()
        referenced: set[str] = set()
        for down_revision in graph.values():
            if isinstance(down_revision, str):
                referenced.add(down_revision)
            elif isinstance(down_revision, tuple):
                referenced.update(down_revision)
        heads = sorted(set(graph) - referenced)
        self.assertEqual(len(heads), 1, f"expected one Alembic head, found {heads}")


if __name__ == "__main__":
    unittest.main()
