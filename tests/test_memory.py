import json

import pytest

from app.answer import (
    MAX_HISTORY,
    answer_question,
    standalone_question,
    trim_history,
)
from app.store import VectorStore
from tests.test_store import CHUNKS, fake_embed


def test_no_history_means_no_rewrite_call():
    def must_not_run(prompt):
        pytest.fail("no rewrite is needed without history")

    question = "What is the waiting period?"
    assert standalone_question(question, [], must_not_run) == question
    assert standalone_question("hi", None, must_not_run) == "hi"


def test_followup_is_rewritten_using_the_history():
    seen = {}

    def rewriter(prompt):
        seen["prompt"] = prompt
        return "What is the co-payment for senior citizens?"

    history = [{"role": "user", "content": "Tell me about co-payment"}]
    result = standalone_question("and for seniors?", history, rewriter)
    assert result == "What is the co-payment for senior citizens?"
    assert "Tell me about co-payment" in seen["prompt"]
    assert "and for seniors?" in seen["prompt"]


@pytest.mark.parametrize(
    "bad_rewrite",
    ["", "   ", "x" * 301, "line one\nline two"],
)
def test_bad_rewrite_falls_back_to_the_original_question(bad_rewrite):
    history = [{"role": "user", "content": "earlier question"}]
    result = standalone_question("and for seniors?", history, lambda p: bad_rewrite)
    assert result == "and for seniors?"


def test_history_is_trimmed_to_recent_turns_and_short_messages():
    history = [{"role": "user", "content": f"m{i}"} for i in range(10)]
    trimmed = trim_history(history)
    assert len(trimmed) == MAX_HISTORY
    assert trimmed[-1]["content"] == "m9"
    long = trim_history([{"role": "user", "content": "x" * 5000}])
    assert len(long[0]["content"]) == 500


def test_answer_uses_the_rewritten_question_for_search_and_prompt(tmp_path):
    seen = {}

    def llm(prompt):
        seen["prompt"] = prompt
        return json.dumps({
            "found": True,
            "answer": "30 days",
            "citations": [{"source": "a.pdf", "page": 1}],
        })

    store = VectorStore(path=tmp_path / "db")
    store.add_chunks(CHUNKS, fake_embed([c["text"] for c in CHUNKS]))
    result = answer_question(
        "and how long is it?",
        store=store,
        embed=lambda texts, task_type=None: fake_embed(texts),
        llm=llm,
        k=2,
        min_score=0.0,
        history=[{"role": "user", "content": "Tell me about waiting periods"}],
        rewriter=lambda prompt: "waiting period days",
    )
    assert result["status"] == "answered"
    assert result["question_used"] == "waiting period days"
    assert "Question: waiting period days" in seen["prompt"]
