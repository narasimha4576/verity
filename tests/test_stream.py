import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.answer import answer_events, answer_question
from app.client import VerityError, ask_stream
from app.main import app, get_embed, get_llm, get_rewriter, get_store
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


def make_store(tmp_path):
    store = VectorStore(path=tmp_path / "db")
    store.add_chunks(CHUNKS, fake_embed([c["text"] for c in CHUNKS]))
    return store


def rewriter(prompt):
    return "waiting period days"


def run(tmp_path, history=None, llm=good_llm, min_score=0.0):
    return list(answer_events(
        "waiting period days",
        store=make_store(tmp_path),
        embed=fake_embed_fn,
        llm=llm,
        k=2,
        min_score=min_score,
        history=history,
        rewriter=rewriter,
    ))


def stage_messages(events):
    return [e["message"] for e in events if e["event"] == "stage"]


# --- the event generator ---

def test_events_are_stages_followed_by_one_result(tmp_path):
    events = run(tmp_path)
    assert events[-1]["event"] == "result"
    assert events[-1]["result"]["status"] == "answered"
    assert all(e["event"] == "stage" for e in events[:-1])


def test_no_understanding_stage_without_history(tmp_path):
    assert not any("Understanding" in m for m in stage_messages(run(tmp_path)))


def test_understanding_stage_appears_with_history(tmp_path):
    history = [{"role": "user", "content": "earlier question"}]
    messages = stage_messages(run(tmp_path, history=history))
    assert any("Understanding" in m for m in messages)


def test_unrelated_question_never_reaches_the_writing_stage(tmp_path):
    def must_not_run(prompt):
        pytest.fail("the AI should not be called for unrelated questions")

    events = run(tmp_path, llm=must_not_run, min_score=0.99)
    assert events[-1]["result"]["status"] == "low_similarity"
    assert not any("Writing" in m for m in stage_messages(events))


def test_answer_question_returns_the_final_result(tmp_path):
    kwargs = {
        "store": make_store(tmp_path),
        "embed": fake_embed_fn,
        "llm": good_llm,
        "k": 2,
        "min_score": 0.0,
        "rewriter": rewriter,
    }
    final = list(answer_events("waiting period days", **kwargs))[-1]["result"]
    assert answer_question("waiting period days", **kwargs) == final


# --- the /ask/stream endpoint ---

@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("MIN_SCORE", "0")
    store = make_store(tmp_path)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_embed] = lambda: fake_embed_fn
    app.dependency_overrides[get_llm] = lambda: good_llm
    app.dependency_overrides[get_rewriter] = lambda: rewriter
    yield TestClient(app)
    app.dependency_overrides.clear()


def events_of(response):
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def test_stream_endpoint_sends_stages_then_the_result(api):
    response = api.post("/ask/stream", json={"question": "waiting period days"})
    assert response.status_code == 200
    events = events_of(response)
    assert events[0]["event"] == "stage"
    assert events[-1]["event"] == "result"
    assert events[-1]["result"]["sources"] == [{"source": "a.pdf", "page": 1}]


def test_stream_reports_a_busy_ai_as_an_error_event(api):
    def down(prompt):
        raise httpx.ConnectError("dropped")

    app.dependency_overrides[get_llm] = lambda: down
    events = events_of(api.post("/ask/stream", json={"question": "waiting period days"}))
    assert events[-1]["event"] == "error"
    assert "busy" in events[-1]["message"]


def test_stream_hides_details_of_unexpected_errors(api):
    def broken(prompt):
        raise RuntimeError("secret internal detail")

    app.dependency_overrides[get_llm] = lambda: broken
    events = events_of(api.post("/ask/stream", json={"question": "waiting period days"}))
    assert events[-1]["event"] == "error"
    assert "secret" not in events[-1]["message"]


def test_stream_rejects_an_empty_question(api):
    assert api.post("/ask/stream", json={"question": ""}).status_code == 422


# --- the client ---

def make_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")


def test_client_yields_each_event_in_order():
    body = "\n".join([
        json.dumps({"event": "stage", "message": "Searching"}),
        json.dumps({"event": "result", "result": {"answer": "x"}}),
    ]) + "\n"

    def handler(request):
        assert request.url.path == "/ask/stream"
        return httpx.Response(200, content=body)

    events = list(ask_stream("q", client=make_client(handler)))
    assert [e["event"] for e in events] == ["stage", "result"]


def test_client_busy_status_gives_a_friendly_error():
    def handler(request):
        return httpx.Response(503, json={"detail": "internal wording"})

    with pytest.raises(VerityError, match="busy"):
        list(ask_stream("q", client=make_client(handler)))


def test_client_api_down_gives_a_clear_message():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(VerityError, match="Cannot reach"):
        list(ask_stream("q", client=make_client(handler)))
