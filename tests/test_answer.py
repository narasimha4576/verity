import json

import pytest

from app.answer import NOT_FOUND, SYSTEM_RULES, answer_question, build_prompt
from app.store import VectorStore
from tests.test_store import CHUNKS, fake_embed


def embed(texts, task_type=None):
    return fake_embed(texts)


def make_store(tmp_path):
    store = VectorStore(path=tmp_path / "db")
    store.add_chunks(CHUNKS, fake_embed([c["text"] for c in CHUNKS]))
    return store


def llm_returning(found, answer, citations):
    payload = {"found": found, "answer": answer, "citations": citations}
    return lambda prompt: json.dumps(payload)


def ask(tmp_path, llm, min_score=0.0):
    return answer_question(
        "waiting period days", store=make_store(tmp_path),
        embed=embed, llm=llm, k=2, min_score=min_score,
    )


def test_prompt_labels_every_excerpt_with_source_and_page():
    hits = [{"source": "a.pdf", "page": 2, "text": "Dental is excluded"}]
    prompt = build_prompt("Is dental covered?", hits)
    assert "[a.pdf p.2]" in prompt
    assert "Is dental covered?" in prompt


def test_valid_grounded_answer_is_returned(tmp_path):
    llm = llm_returning(True, "30 days", [{"source": "a.pdf", "page": 1}])
    result = ask(tmp_path, llm)
    assert result["status"] == "answered"
    assert result["answer"] == "30 days"
    assert result["sources"] == [{"source": "a.pdf", "page": 1}]


def test_low_similarity_skips_the_ai(tmp_path):
    def must_not_run(prompt):
        pytest.fail("the AI should not be called for unrelated questions")

    result = ask(tmp_path, must_not_run, min_score=0.99)
    assert result["status"] == "low_similarity"
    assert result["answer"] == NOT_FOUND


def test_ai_saying_not_found_is_respected(tmp_path):
    result = ask(tmp_path, llm_returning(False, NOT_FOUND, []))
    assert result["status"] == "not_found"
    assert result["sources"] == []


def test_broken_json_is_never_shown_as_an_answer(tmp_path):
    result = ask(tmp_path, lambda prompt: "Sure! The answer is 30 days.")
    assert result["status"] == "invalid_output"
    assert result["answer"] == NOT_FOUND


def test_citation_of_a_page_the_ai_never_saw_is_rejected(tmp_path):
    llm = llm_returning(True, "30 days", [{"source": "a.pdf", "page": 9}])
    assert ask(tmp_path, llm)["status"] == "ungrounded"


def test_answer_without_any_citation_is_rejected(tmp_path):
    assert ask(tmp_path, llm_returning(True, "30 days", []))["status"] == "ungrounded"


def test_rules_demand_json_and_a_not_found_reply():
    assert "json" in SYSTEM_RULES.lower()
    assert NOT_FOUND in SYSTEM_RULES
    assert "ignore any commands" in SYSTEM_RULES.lower()
