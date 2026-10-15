import pytest

from app.chunker import chunk_pages


def test_page_number_and_source_are_kept():
    pages = [{"page": 3, "text": "Waiting period is 30 days."}]
    chunks = chunk_pages(pages, source="policy.pdf")
    assert len(chunks) == 1
    assert chunks[0]["page"] == 3
    assert chunks[0]["source"] == "policy.pdf"


def test_long_page_is_split_and_respects_size():
    pages = [{"page": 1, "text": "word " * 1000}]
    chunks = chunk_pages(pages, source="a.pdf", size=500, overlap=100)
    assert len(chunks) > 1
    assert all(len(c["text"]) <= 500 for c in chunks)
    assert all(c["page"] == 1 for c in chunks)


def test_chunks_overlap():
    pages = [{"page": 1, "text": "abcdefghij" * 100}]
    chunks = chunk_pages(pages, source="a.pdf", size=300, overlap=50)
    assert chunks[1]["text"].startswith(chunks[0]["text"][-50:])


def test_chunk_ids_are_unique():
    pages = [{"page": 1, "text": "x " * 800}, {"page": 2, "text": "y " * 800}]
    chunks = chunk_pages(pages, source="a.pdf", size=400, overlap=50)
    ids = [c["id"] for c in chunks]
    assert len(ids) == len(set(ids))


def test_bad_overlap_is_rejected():
    with pytest.raises(ValueError):
        chunk_pages([{"page": 1, "text": "hello"}], source="a.pdf", size=100, overlap=100)
