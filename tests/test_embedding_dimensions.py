from __future__ import annotations

import unittest

from app.config import settings
from app.models import DocumentChunk
from app.services.embeddings import EmbeddingServiceError, _normalize_embeddings


class EmbeddingDimensionsTests(unittest.TestCase):
    def test_document_chunk_vector_uses_configured_dimension(self) -> None:
        vector_type = DocumentChunk.__table__.c.embedding.type
        self.assertEqual(getattr(vector_type, "dim", None), settings.embedding_dimensions)

    def test_normalize_embeddings_rejects_dimension_mismatch(self) -> None:
        with self.assertRaises(EmbeddingServiceError) as ctx:
            _normalize_embeddings([[0.1, 0.2, 0.3]], expected_text_count=1)
        self.assertIn("Embedding dimension mismatch", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
