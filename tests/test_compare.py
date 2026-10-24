from benchmark.compare import compare, format_comparison

ANSWERABLE = {
    "id": "A1", "category": "policy_fact", "question": "How long?", "answerable": True,
    "expected": [{"source": "a.pdf", "page": 1}], "answer_keys": [["36 months"]],
}
UNANSWERABLE = {"id": "U1", "category": "tempting_not_in_docs", "question": "Max speed?", "answerable": False}


def rec(status="answered", answer="36 months", error=None):
    return {
        "status": status, "answer": answer, "error": error, "question_used": "q",
        "sources": [{"source": "a.pdf", "page": 1}], "retrieved": [{"source": "a.pdf", "page": 1}],
    }


def test_a_fixed_question_is_reported_as_fixed():
    before = {"A1": rec(), "U1": rec(answer="2 GB a day")}
    after = {"A1": rec(), "U1": rec(status="not_found", answer="I could not find this.")}
    result = compare([ANSWERABLE, UNANSWERABLE], before, after)
    assert result["fixed"] == ["U1"]
    assert result["broke"] == [] and result["still_failing"] == []


def test_a_question_that_got_worse_is_reported_as_broke():
    before = {"A1": rec()}
    after = {"A1": rec(status="not_found", answer="I could not find this.")}
    assert compare([ANSWERABLE], before, after)["broke"] == ["A1"]


def test_a_question_failing_in_both_runs_is_still_failing():
    wrong = rec(answer="12 months")
    assert compare([ANSWERABLE], {"A1": wrong}, {"A1": wrong})["still_failing"] == ["A1"]


def test_only_shared_questions_are_compared_and_errors_are_skipped():
    before = {"A1": rec(), "U1": rec(error="ConnectError")}
    after = {"A1": rec(), "U1": rec(status="not_found")}
    result = compare([ANSWERABLE, UNANSWERABLE], before, after)
    assert [q["id"] for q in result["questions"]] == ["A1"]
    assert result["skipped"] == 1
    only_after = compare([ANSWERABLE], {}, {"A1": rec()})
    assert only_after["questions"] == []


def test_the_report_names_the_runs_and_lists_the_changes():
    before = {"A1": rec(), "U1": rec(answer="2 GB a day")}
    after = {"A1": rec(), "U1": rec(status="not_found")}
    result = compare([ANSWERABLE, UNANSWERABLE], before, after)
    text = format_comparison("v2", "day18", result)
    assert "| Metric | v2 | day18 |" in text
    assert "## Fixed" in text and "U1: Max speed?" in text
