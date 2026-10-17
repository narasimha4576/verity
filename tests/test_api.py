import json

import httpx
import pytest
from fastapi.testclient import TestClient
from pypdf.errors import PdfReadError

from app.main import app, get_embed, get_llm, get_store, get_upload_dir
from app.store import VectorStore
from tests.test_store import CHUNKS, fake_embed


def fake_embed_fn(texts, task_type=None):
    return fake_embed(texts)


def good_llm(prompt):
    return json.dumps({
        "found": True,
        "answer": "30 days",
        "citations": [{"source": "a.pdf", "page": 1}],
    })


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MIN_SCORE", "0")
    store = VectorStore(path=tmp_path / "db")
    store.add_chunks(CHUNKS, fake_embed([c["text"] for c in CHUNKS]))
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_embed] = lambda: fake_embed_fn
    app.dependency_overrides[get_llm] = lambda: good_llm
    app.dependency_overrides[get_upload_dir] = lambda: tmp_path / "uploads"
    yield TestClient(app)
    app.dependency_overrides.clear()


def pdf_upload(name="policy.pdf", content=b"%PDF-1.4 fake"):
    return {"file": (name, content, "application/pdf")}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_upload_valid_pdf_is_ingested(client, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.ingest.load_pdf", lambda p: [{"page": 1, "text": "Maternity cover is 50000"}]
    )
    response = client.post("/upload", files=pdf_upload())
    assert response.status_code == 200
    assert response.json() == {"filename": "policy.pdf", "chunks": 1}
    assert (tmp_path / "uploads" / "policy.pdf").exists()


def test_upload_rejects_non_pdf_name(client):
    assert client.post("/upload", files=pdf_upload("notes.txt")).status_code == 400


def test_upload_rejects_text_renamed_to_pdf(client):
    response = client.post("/upload", files=pdf_upload(content=b"just some text"))
    assert response.status_code == 400


def test_upload_rejects_oversized_file(client, monkeypatch):
    monkeypatch.setattr("app.main.MAX_UPLOAD_BYTES", 10)
    response = client.post("/upload", files=pdf_upload(content=b"%PDF" + b"x" * 50))
    assert response.status_code == 413


def test_upload_corrupt_pdf_gives_422(client, monkeypatch):
    def broken(path):
        raise PdfReadError("bad file")

    monkeypatch.setattr("app.ingest.load_pdf", broken)
    assert client.post("/upload", files=pdf_upload()).status_code == 422


def test_upload_path_trick_in_name_is_neutralised(client, monkeypatch, tmp_path):
    monkeypatch.setattr("app.ingest.load_pdf", lambda p: [{"page": 1, "text": "hello world"}])
    response = client.post("/upload", files=pdf_upload("../../evil.pdf"))
    assert response.json()["filename"] == "evil.pdf"
    assert (tmp_path / "uploads" / "evil.pdf").exists()


def test_ask_returns_status_answer_and_sources(client):
    body = client.post("/ask", json={"question": "waiting period days"}).json()
    assert body["status"] == "answered"
    assert body["sources"] == [{"source": "a.pdf", "page": 1}]


def test_ask_rejects_empty_and_too_long_questions(client):
    assert client.post("/ask", json={"question": ""}).status_code == 422
    assert client.post("/ask", json={"question": "x" * 501}).status_code == 422


def test_ask_gives_503_when_the_ai_is_temporarily_down(client):
    def down(prompt):
        raise httpx.ConnectError("dropped")

    app.dependency_overrides[get_llm] = lambda: down
    response = client.post("/ask", json={"question": "waiting period days"})
    assert response.status_code == 503
