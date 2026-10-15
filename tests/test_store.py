import hashlib
import math

from app.ingest import ingest
from app.store import VectorStore


def fake_embed(texts, dim=256):
    vectors = []
    for text in texts:
        v = [0.0] * dim
        for word in text.lower().split():
            word = word.strip(".,:;()")
            v[int(hashlib.md5(word.encode()).hexdigest(), 16) % dim] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        vectors.append([x / norm for x in v])
    return vectors


CHUNKS = [
    {"id": "a-p1-0", "source": "a.pdf", "page": 1,
     "text": "Initial waiting period is 30 days for any illness"},
    {"id": "a-p2-0", "source": "a.pdf", "page": 2,
     "text": "Dental treatment is excluded unless caused by an accident"},
    {"id": "a-p3-0", "source": "a.pdf", "page": 3,
     "text": "Cashless claims must be notified 48 hours before admission"},
]


def make_store(tmp_path):
    store = VectorStore(path=tmp_path / "db")
    store.add_chunks(CHUNKS, fake_embed([c["text"] for c in CHUNKS]))
    return store


def test_search_finds_the_right_chunk_with_page_and_source(tmp_path):
    store = make_store(tmp_path)
    hits = store.search(fake_embed(["waiting period days"])[0], k=2)
    assert hits[0]["page"] == 1
    assert hits[0]["source"] == "a.pdf"
    assert hits[0]["score"] > hits[1]["score"]


def test_adding_the_same_chunks_twice_does_not_duplicate(tmp_path):
    store = make_store(tmp_path)
    store.add_chunks(CHUNKS, fake_embed([c["text"] for c in CHUNKS]))
    assert store.count() == 3


def test_empty_store_returns_no_hits(tmp_path):
    store = VectorStore(path=tmp_path / "empty")
    assert store.search(fake_embed(["anything"])[0]) == []


def test_ingest_reads_chunks_and_stores_them(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.ingest.load_pdf",
        lambda path: [{"page": 5, "text": "Co-payment is 10 percent after age 60"}],
    )
    store = VectorStore(path=tmp_path / "ing")
    assert ingest("fake.pdf", store=store, embed=fake_embed) == 1
    hit = store.search(fake_embed(["co-payment age"])[0])[0]
    assert hit["page"] == 5
    assert hit["source"] == "fake.pdf"
