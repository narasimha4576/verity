import pytest

from app.router import decide


def result(status):
    return {"status": status, "answer": "x", "sources": []}


@pytest.mark.parametrize("status", ["not_found", "low_similarity", "no_documents"])
def test_a_gap_in_the_documents_goes_to_the_web_when_allowed(status):
    use_web, reason = decide(result(status), allow_web=True)
    assert use_web is True
    assert "do not answer" in reason


def test_a_document_answer_never_goes_to_the_web():
    assert decide(result("answered"), allow_web=True)[0] is False


@pytest.mark.parametrize("status", ["ungrounded", "invalid_output"])
def test_a_rejected_answer_is_a_system_problem_not_a_gap(status):
    use_web, reason = decide(result(status), allow_web=True)
    assert use_web is False
    assert "rejected" in reason


@pytest.mark.parametrize("status", ["not_found", "low_similarity", "no_documents", "answered"])
def test_the_web_stays_off_unless_it_is_allowed(status):
    use_web, reason = decide(result(status), allow_web=False)
    assert use_web is False
    assert "switched off" in reason


def test_choosing_documents_means_documents_only():
    use_web, reason = decide(result("not_found"), allow_web=True, sources=["a.pdf"])
    assert use_web is False
    assert "chosen documents" in reason


def test_an_empty_source_list_is_not_a_restriction():
    assert decide(result("not_found"), allow_web=True, sources=[])[0] is True
    assert decide(result("not_found"), allow_web=True, sources=None)[0] is True
