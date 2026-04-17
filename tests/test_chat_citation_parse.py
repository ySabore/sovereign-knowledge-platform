"""Stored chat citations may be full RAG dicts or legacy seed shapes."""

from uuid import UUID, uuid4

from app.routers.chat import _parse_chat_citation


def test_parse_full_rag_citation_roundtrip():
    doc_id = uuid4()
    chunk_id = uuid4()
    raw = {
        "chunk_id": str(chunk_id),
        "document_id": str(doc_id),
        "document_filename": "a.pdf",
        "chunk_index": 2,
        "page_number": 5,
        "score": 0.91,
        "quote": "hello",
    }
    c = _parse_chat_citation(raw)
    assert c is not None
    assert c.chunk_id == chunk_id
    assert c.document_id == doc_id
    assert c.document_filename == "a.pdf"
    assert c.chunk_index == 2
    assert c.page_number == 5
    assert c.score == 0.91
    assert c.quote == "hello"


def test_parse_legacy_seed_shape_filename_only():
    doc_id = uuid4()
    raw = {"document_id": str(doc_id), "filename": "Conflict_Check.pdf"}
    c = _parse_chat_citation(raw)
    assert c is not None
    assert c.document_id == doc_id
    assert c.document_filename == "Conflict_Check.pdf"
    assert c.chunk_index == 0
    assert c.page_number is None
    assert c.score == 0.0
    assert c.quote == ""
    assert isinstance(c.chunk_id, UUID)
    c2 = _parse_chat_citation(raw)
    assert c2 is not None
    assert c2.chunk_id == c.chunk_id


def test_parse_rejects_non_dict_and_missing_document_id():
    assert _parse_chat_citation("x") is None
    assert _parse_chat_citation({"filename": "only.pdf"}) is None
