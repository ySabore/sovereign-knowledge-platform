from __future__ import annotations

import ast
import unittest
from pathlib import Path


VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _literal_assignment(module: ast.Module, name: str) -> object:
    for node in module.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"missing {name!r} assignment")


class AlembicRevisionTests(unittest.TestCase):
    def test_revisions_are_unique_and_linear(self) -> None:
        revisions: dict[str, str | None] = {}

        for path in sorted(VERSIONS_DIR.glob("*.py")):
            module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            revision = _literal_assignment(module, "revision")
            down_revision = _literal_assignment(module, "down_revision")

            self.assertIsInstance(revision, str, path.name)
            self.assertTrue(revision, path.name)
            self.assertNotIn(revision, revisions, f"duplicate revision {revision!r} in {path.name}")

            if isinstance(down_revision, tuple):
                self.fail(f"{path.name} creates a branched migration history via down_revision={down_revision!r}")
            self.assertTrue(isinstance(down_revision, str) or down_revision is None, path.name)
            revisions[revision] = down_revision

        self.assertGreater(len(revisions), 0)

        bases = [revision for revision, down_revision in revisions.items() if down_revision is None]
        self.assertEqual(["001"], bases)

        referenced_revisions = [down_revision for down_revision in revisions.values() if down_revision is not None]
        for down_revision in referenced_revisions:
            self.assertIn(down_revision, revisions)

        heads = set(revisions) - set(referenced_revisions)
        self.assertEqual({"022"}, heads)


if __name__ == "__main__":
    unittest.main()
