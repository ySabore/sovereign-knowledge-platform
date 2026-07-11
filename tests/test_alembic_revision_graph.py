from __future__ import annotations

import ast
from pathlib import Path


VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _literal_assignment(module: ast.Module, name: str) -> str | tuple[str, ...] | None:
    for node in module.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing {name!r} assignment")


def test_alembic_revisions_are_unique_and_linked() -> None:
    revisions: dict[str, Path] = {}
    down_revisions: dict[str, str | tuple[str, ...] | None] = {}

    for path in sorted(VERSIONS_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        revision = _literal_assignment(module, "revision")
        down_revision = _literal_assignment(module, "down_revision")

        assert isinstance(revision, str), f"{path.name} has invalid revision {revision!r}"
        assert revision not in revisions, (
            f"Duplicate Alembic revision {revision!r}: "
            f"{revisions[revision].name} and {path.name}"
        )
        revisions[revision] = path
        down_revisions[revision] = down_revision

    assert revisions, "No Alembic revisions found"

    for revision, down_revision in down_revisions.items():
        parents: tuple[str, ...]
        if down_revision is None:
            parents = ()
        elif isinstance(down_revision, str):
            parents = (down_revision,)
        else:
            parents = down_revision

        for parent in parents:
            assert parent in revisions, f"{revision!r} references missing down_revision {parent!r}"
