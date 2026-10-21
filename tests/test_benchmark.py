import json
from pathlib import Path

import pytest

from app.loader import load_pdf
from benchmark.run import run_questions
from benchmark.scoring import (
    CATEGORIES,
    format_report,
    keys_match,
    score_question,
    summarize,
)

BENCH = Path(__file__).resolve().parent.parent / "benchmark"
QUESTIONS = json.loads((BENCH / "questions.json").read_text(encoding="utf-8"))
PDF_PAGES = {
    pdf.name: {p["page"]: " ".join(p["text"].lower().split()) for p in load_pdf(pdf)}
    for pdf in (BENCH / "docs").glob("*.pdf")
}


# ---------- the ground truth is checked against the real documents ----------

def test_benchmark_is_big_enough_and_balanced():
    assert len(QUESTIONS) >= 40
    assert sum(1 for q in QUESTIONS if not q["answerable"]) >= 8
    assert {q["category"] for q in QUESTIONS} == set(CATEGORIES)


def test_question_ids_are_unique_and_well_formed():
    ids = [q["id"] for q in QUESTIONS]
    assert len(ids) == len(set(ids))
    for q in QUESTIONS:
        assert q["question"].strip()
        assert len(q["question"]) <= 500
        for turn in q.get("history", []):
            assert turn["role"] in ("user", "assistant")
        if q["answerable"]:
            assert q["expected"] and q["answer_keys"]
        else:
            assert "expected" not in q


def test_every_expected_page_exists_and_contains_the_answer():
    for q in QUESTIONS:
        if not q["answerable"]:
            continue
        texts = []
        for item in q["expected"]:
            pages = PDF_PAGES[item["source"]]
            assert item["page"] in pages, f"{q['id']}: no page {item['page']}"
            texts.append(pages[item["page"]])
        combined = " ".join(texts)
        for group in q["answer_keys"]:
            # the first spelling in each group is the one printed in the document
            assert group[0].lower() in combined, f"{q['id']}: '{group[0]}' not on the labelled page"


def test_source_filters_name_real_documents():
    for q in QUESTIONS:
        for name in q.get("sources", []):
            assert name in PDF_PAGES


# ---------- scoring ----------

ANSWERABLE = {
    "id": "X1", "category": "policy_fact", "question": "How long?", "answerable": True,
    "expected": [{"source": "a.pdf", "page": 2}],
    "answer_keys": [["36 months", "three years"]],
}
UNANSWERABLE = {"id": "X2", "category": "not_in_documents", "question": "Premium?", "answerable": False}


def record(status="answered", answer="It is 36 months.", sources=None, retrieved=None, used="How long?"):
    return {
        "status": status, "answer": answer, "error": None, "question_used": used,
        "sources": [{"source": "a.pdf", "page": 2}] if sources is None else sources,
        "retrieved": [{"source": "a.pdf", "page": 2}] if retrieved is None else retrieved,
    }


def test_keys_match_needs_one_spelling_from_every_group():
    groups = [["36 months", "three years"], ["50,000"]]
    assert keys_match("After THREE   years, up to Rs 50,000.", groups)
    assert not keys_match("After three years.", groups)


def test_correct_answer():
    assert score_question(ANSWERABLE, record())["outcome"] == "correct"


def test_wrong_answer_that_was_shown_is_a_silent_error():
    assert score_question(ANSWERABLE, record(answer="It is 12 months."))["outcome"] == "wrong_answer"


def test_right_answer_with_the_wrong_page_is_miscited():
    result = score_question(ANSWERABLE, record(sources=[{"source": "a.pdf", "page": 3}]))
    assert result["outcome"] == "miscited"


def test_refusing_an_answerable_question_is_a_false_refusal():
    result = score_question(ANSWERABLE, record(status="not_found"))
    assert result["outcome"] == "false_refusal"
    assert result["retrieval_hit"] is True


def test_retrieval_hit_is_tracked_separately_from_the_answer():
    result = score_question(ANSWERABLE, record(retrieved=[{"source": "a.pdf", "page": 1}]))
    assert result["retrieval_hit"] is False


@pytest.mark.parametrize("status", ["not_found", "low_similarity", "ungrounded", "invalid_output"])
def test_refusals_of_unanswerable_questions_are_correct(status):
    assert score_question(UNANSWERABLE, record(status=status))["outcome"] == "correct_refusal"


def test_answering_an_unanswerable_question_is_a_hallucination():
    assert score_question(UNANSWERABLE, record())["outcome"] == "hallucination"


def test_a_changed_question_is_flagged_when_there_was_a_chat():
    q = dict(ANSWERABLE, history=[{"role": "user", "content": "earlier"}])
    assert score_question(q, record(used="How long, for the loan?"))["rewrite_changed"] is True
    assert score_question(q, record())["rewrite_changed"] is False


def test_summary_counts_and_excludes_errors():
    questions = [ANSWERABLE, dict(ANSWERABLE, id="X3"), UNANSWERABLE, dict(UNANSWERABLE, id="X4")]
    records = {
        "X1": record(),
        "X3": record(answer="12 months"),
        "X2": record(status="not_found"),
        "X4": {"error": "ConnectError", "status": None},
    }
    s = summarize(questions, records)
    assert (s["answerable"], s["unanswerable"], s["errors"]) == (2, 1, 1)
    assert (s["correct"], s["wrong_answer"], s["correct_refusal"]) == (1, 1, 1)
    assert s["silent_errors"] == 1
    assert s["passed"] == 2 and s["valid"] == 3


def test_report_lists_problems_for_a_human_to_review():
    questions = [ANSWERABLE]
    records = {"X1": record(answer="It is 12 months.")}
    text = format_report(summarize(questions, records), questions, records)
    assert "Questions to review" in text
    assert "X1 [wrong_answer]" in text
    assert "12 months" in text


# ---------- the runner ----------

def fake_answer(q):
    return {"status": "answered", "answer": "ok", "sources": [], "question_used": q["question"]}


def fake_retrieve(q, used):
    return []


def test_runner_records_a_failure_and_keeps_going_without_saving_the_message():
    def flaky(q):
        if q["id"] == "X1":
            raise RuntimeError("secret detail from the API")
        return fake_answer(q)

    records = run_questions([ANSWERABLE, UNANSWERABLE], flaky, fake_retrieve, sleep=lambda s: None)
    assert records["X1"]["error"] == "RuntimeError"
    assert "secret" not in json.dumps(records)
    assert records["X2"]["error"] is None


def test_runner_skips_questions_that_already_have_a_result():
    calls = []

    def counting(q):
        calls.append(q["id"])
        return fake_answer(q)

    done = {"X1": record()}
    records = run_questions([ANSWERABLE, UNANSWERABLE], counting, fake_retrieve,
                            done=done, sleep=lambda s: None)
    assert calls == ["X2"]
    assert set(records) == {"X1", "X2"}


def test_runner_saves_progress_after_every_question():
    saved = []
    run_questions([ANSWERABLE, UNANSWERABLE], fake_answer, fake_retrieve,
                  on_record=lambda r: saved.append(len(r)), sleep=lambda s: None)
    assert saved == [1, 2]
