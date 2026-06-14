from __future__ import annotations

import ast
from pathlib import Path


def _literal_assignment(module: ast.Module, name: str) -> str | None:
    for node in module.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            if isinstance(node.value, ast.Constant):
                return str(node.value.value)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name and isinstance(node.value, ast.Constant):
                    return str(node.value.value)
    return None


def test_alembic_revision_ids_are_unique() -> None:
    revisions: dict[str, Path] = {}
    for path in Path("alembic/versions").glob("*.py"):
        module = ast.parse(path.read_text(encoding="utf-8"))
        revision = _literal_assignment(module, "revision")
        assert revision, f"{path} does not define a literal revision"
        assert revision not in revisions, f"duplicate revision {revision!r}: {revisions[revision]} and {path}"
        revisions[revision] = path

