from __future__ import annotations

import unittest
from uuid import uuid4

from app.services.rag.rrf import reciprocal_rank_fusion
from app.services.rag.types import RetrievalHit


def _hit(cid: str, score: float = 0.5) -> RetrievalHit:
    u = uuid4()
    return RetrievalHit(
        chunk_id=u,
        document_id=uuid4(),
        document_filename="x.pdf",
        chunk_index=0,
        page_number=1,
        score=score,
        content=cid,
    )


class RrfTests(unittest.TestCase):
    def test_rrf_prefers_chunk_in_both_lists(self) -> None:
        a = _hit("only-a")
        b = _hit("both")
        c = _hit("only-c")
        vec = [a, b]
        fts = [c, b]
        merged = reciprocal_rank_fusion([vec, fts], k=60)
        self.assertGreaterEqual(len(merged), 1)
        contents = [m.content for m in merged]
        self.assertIn("both", contents)
        self.assertEqual(merged[0].content, "both")

    def test_single_list_passthrough_order(self) -> None:
        h1 = _hit("first")
        h2 = _hit("second")
        out = reciprocal_rank_fusion([[h1, h2]], k=60)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0].content, "first")


if __name__ == "__main__":
    unittest.main()
