import pytest

from app.answer import NO_DOCUMENTS, answer_events, answer_question
from app.store import VectorStore


def must_not_run(*args, **kwargs):
    pytest.fail("nothing should be called when there are no documents")


def test_empty_library_gives_a_clear_message_and_calls_nothing(tmp_path):
    store = VectorStore(path=tmp_path / "empty")
    result = answer_question(
        "anything",
        store=store,
        embed=must_not_run,
        llm=must_not_run,
        rewriter=must_not_run,
    )
    assert result["status"] == "no_documents"
    assert result["answer"] == NO_DOCUMENTS


def test_empty_library_is_checked_before_a_follow_up_is_rewritten(tmp_path):
    store = VectorStore(path=tmp_path / "empty")
    events = list(
        answer_events(
            "and for seniors?",
            store=store,
            embed=must_not_run,
            llm=must_not_run,
            rewriter=must_not_run,
            history=[{"role": "user", "content": "earlier question"}],
        )
    )
    assert [e["event"] for e in events] == ["result"]
