import json

import pytest
from fastapi.testclient import TestClient

from app.client import ask as client_ask
from app.client import delete_document, list_documents
from app.ingest import ingest
from app.main import app, get_embed, get_llm, get_rewriter, get_store, get_upload_dir
from app.store import VectorStore
from tests.test_client import make_client
from tests.test_store import CHUNKS, fake_embed

B_CHUNK = {
    "id": "b-p1-0",
    "source": "b.pdf",
    "page": 1,
    "text": "Maternity cover is limited to fifty thousand rupees",
}
ALL_CHUNKS = CHUNKS + [B_CHUNK]


def make_two_doc_store(tmp_path):
    store = VectorStore(path=tmp_path / "db")
    store.add_chunks(ALL_CHUNKS, fake_embed([c["text"] for c in ALL_CHUNKS]))
    return store


def query():
    return fake_embed(["waiting period days"])[0]


# --- the store ---

def test_list_sources_counts_chunks_per_document(tmp_path):
    store = make_two_doc_store(tmp_path)
    assert store.list_sources() == [
        {"source": "a.pdf", "chunks": 3},
        {"source": "b.pdf", "chunks": 1},
    ]


def test_delete_source_removes_only_that_document(tmp_path):
    store = make_two_doc_store(tmp_path)
    assert store.delete_source("a.pdf") == 3
    assert store.list_sources() == [{"source": "b.pdf", "chunks": 1}]
    assert store.delete_source("missing.pdf") == 0


def test_replace_source_leaves_no_stale_chunks(tmp_path):
    store = make_two_doc_store(tmp_path)
    new_chunk = {"id": "a-p1-0", "source": "a.pdf", "page": 1, "text": "brand new text"}
    store.replace_source("a.pdf", [new_chunk], fake_embed([new_chunk["text"]]))
    assert {"source": "a.pdf", "chunks": 1} in store.list_sources()


def test_search_can_be_limited_to_chosen_documents(tmp_path):
    store = make_two_doc_store(tmp_path)
    hits = store.search(query(), k=4, sources=["b.pdf"])
    assert len(hits) == 1
    assert all(h["source"] == "b.pdf" for h in hits)


def test_search_with_an_unknown_document_returns_nothing(tmp_path):
    store = make_two_doc_store(tmp_path)
    assert store.search(query(), k=4, sources=["nope.pdf"]) == []


# --- ingest ---

def test_ingest_replaces_the_old_version_of_a_document(tmp_path, monkeypatch):
    store = VectorStore(path=tmp_path / "db")
    monkeypatch.setattr("app.ingest.load_pdf", lambda p: [{"page": 1, "text": "word " * 400}])
    assert ingest("doc.pdf", store=store, embed=fake_embed) > 1
    monkeypatch.setattr("app.ingest.load_pdf", lambda p: [{"page": 1, "text": "short text"}])
    assert ingest("doc.pdf", store=store, embed=fake_embed) == 1
    assert store.count() == 1


def test_a_failed_embedding_keeps_the_old_version(tmp_path, monkeypatch):
    store = VectorStore(path=tmp_path / "db")
    monkeypatch.setattr("app.ingest.load_pdf", lambda p: [{"page": 1, "text": "word " * 400}])
    ingest("doc.pdf", store=store, embed=fake_embed)
    before = store.count()

    def broken(texts, task_type=None):
        raise RuntimeError("network down")

    monkeypatch.setattr("app.ingest.load_pdf", lambda p: [{"page": 1, "text": "short text"}])
    with pytest.raises(RuntimeError):
        ingest("doc.pdf", store=store, embed=broken)
    assert store.count() == before


# --- the API ---

def good_llm(prompt):
    return json.dumps({
        "found": True,
        "answer": "30 days",
        "citations": [{"source": "a.pdf", "page": 1}],
    })


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("MIN_SCORE", "0")
    store = make_two_doc_store(tmp_path)
    uploads = tmp_path / "uploads"
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_embed] = lambda: (lambda texts, task_type=None: fake_embed(texts))
    app.dependency_overrides[get_llm] = lambda: good_llm
    app.dependency_overrides[get_rewriter] = lambda: (lambda prompt: "waiting period days")
    app.dependency_overrides[get_upload_dir] = lambda: uploads
    yield TestClient(app), uploads
    app.dependency_overrides.clear()


def test_documents_endpoint_lists_what_is_stored(api):
    client, _ = api
    names = [d["source"] for d in client.get("/documents").json()["documents"]]
    assert names == ["a.pdf", "b.pdf"]


def test_delete_removes_chunks_and_the_uploaded_file(api):
    client, uploads = api
    uploads.mkdir()
    (uploads / "a.pdf").write_bytes(b"%PDF-1.4")
    response = client.delete("/documents/a.pdf")
    assert response.status_code == 200
    assert response.json()["chunks_removed"] == 3
    assert not (uploads / "a.pdf").exists()
    names = [d["source"] for d in client.get("/documents").json()["documents"]]
    assert names == ["b.pdf"]


def test_delete_of_an_unknown_document_gives_404(api):
    client, _ = api
    assert client.delete("/documents/ghost.pdf").status_code == 404


def test_ask_limited_to_the_right_document_is_answered(api):
    client, _ = api
    body = client.post(
        "/ask", json={"question": "waiting period days", "sources": ["a.pdf"]}
    ).json()
    assert body["status"] == "answered"


def test_citation_outside_the_chosen_documents_is_rejected(api):
    client, _ = api
    # The AI cites a.pdf, but the search was limited to b.pdf
    body = client.post(
        "/ask", json={"question": "waiting period days", "sources": ["b.pdf"]}
    ).json()
    assert body["status"] == "ungrounded"


def test_ask_rejects_too_many_documents(api):
    client, _ = api
    names = [f"d{i}.pdf" for i in range(21)]
    response = client.post("/ask", json={"question": "hi", "sources": names})
    assert response.status_code == 422


# --- the client ---

def test_list_documents_returns_the_list():
    import httpx

    def handler(request):
        assert request.method == "GET"
        return httpx.Response(200, json={"documents": [{"source": "a.pdf", "chunks": 3}]})

    assert list_documents(client=make_client(handler)) == [{"source": "a.pdf", "chunks": 3}]


def test_delete_document_encodes_the_name():
    import httpx

    def handler(request):
        assert request.method == "DELETE"
        assert b"my%20policy.pdf" in request.url.raw_path
        return httpx.Response(200, json={"filename": "my policy.pdf", "chunks_removed": 2})

    assert delete_document("my policy.pdf", client=make_client(handler))["chunks_removed"] == 2


def test_ask_sends_the_chosen_documents():
    import httpx

    seen = {}

    def handler(request):
        seen["body"] = request.content
        return httpx.Response(
            200,
            json={"status": "answered", "answer": "x", "sources": [], "question_used": "q"},
        )

    client_ask("q", sources=["a.pdf"], client=make_client(handler))
    assert b'"sources"' in seen["body"]
    assert b"a.pdf" in seen["body"]
