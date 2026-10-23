import pytest

from app.websearch import (
    MAX_QUERY_CHARS,
    WebSearcher,
    WebSearchError,
    clean_query,
    clean_results,
    tidy,
)


class RatelimitException(Exception):  # same name as the real library's error
    pass


def raw(url="https://example.com/a", title="Title", body="Some text about the topic."):
    return {"href": url, "title": title, "body": body}


# ---------- the query ----------

def test_query_is_trimmed_and_flattened_to_one_line():
    assert clean_query("  how   long\n is\ta  match ") == "how long is a match"


@pytest.mark.parametrize("bad", ["", "  ", "ab", None])
def test_short_or_empty_queries_are_rejected(bad):
    with pytest.raises(ValueError, match="too short"):
        clean_query(bad)


def test_long_queries_are_rejected_so_document_text_cannot_leak():
    pasted = "The prepayment charge is 2% of the outstanding principal. " * 10
    with pytest.raises(ValueError, match="too long"):
        clean_query(pasted)
    assert len(clean_query("a" * MAX_QUERY_CHARS)) == MAX_QUERY_CHARS


def test_invisible_characters_are_removed():
    assert tidy("ig\u200bnore\u202e this", 100) == "ignore this"


# ---------- the results ----------

def test_only_http_and_https_links_are_kept():
    items = [
        raw("javascript:alert(1)"),
        raw("data:text/html,hi"),
        raw("ftp://example.com/file"),
        raw("/relative/path"),
        raw("https://ok.example.com/page"),
        raw("http://also-ok.example.com"),
    ]
    urls = [r["url"] for r in clean_results(items, 10)]
    assert urls == ["https://ok.example.com/page", "http://also-ok.example.com"]


def test_links_with_embedded_credentials_are_dropped():
    assert clean_results([raw("https://bank.com@evil.example/login")], 5) == []


def test_duplicates_are_removed_ignoring_a_trailing_slash():
    items = [raw("https://example.com/a"), raw("https://example.com/a/")]
    assert len(clean_results(items, 5)) == 1


def test_results_without_text_are_dropped():
    assert clean_results([raw(body=""), {"href": "https://example.com"}], 5) == []


def test_text_is_shortened_and_cleaned():
    item = raw(title="T" * 500, body="word " * 500)
    result = clean_results([item], 5)[0]
    assert len(result["title"]) <= 160
    assert len(result["snippet"]) <= 400
    assert "\n" not in result["snippet"]


def test_domain_is_extracted_and_www_removed():
    result = clean_results([raw("https://www.Example.com/page")], 5)[0]
    assert result["domain"] == "example.com"


def test_the_other_common_key_names_are_understood():
    item = {"url": "https://example.com", "snippet": "Plain snippet", "title": "T"}
    assert clean_results([item], 5)[0]["snippet"] == "Plain snippet"


def test_max_results_and_junk_items_are_handled():
    items = [raw(f"https://example.com/{i}") for i in range(10)] + ["junk", None, 5]
    assert len(clean_results(items, 3)) == 3
    assert clean_results(None, 3) == []


# ---------- the searcher ----------

class Clock:
    def __init__(self):
        self.now = 1000.0
        self.slept = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def make(backend, **kwargs):
    clock = Clock()
    searcher = WebSearcher(backend=backend, clock=clock, sleep=clock.sleep,
                           retry_delay=0, **kwargs)
    return searcher, clock


def test_search_returns_cleaned_results():
    searcher, _ = make(lambda q, n: [raw(), {"href": "javascript:x"}])
    results = searcher.search("python tutorials")
    assert [r["url"] for r in results] == ["https://example.com/a"]


def test_same_question_is_answered_from_the_cache():
    calls = []

    def backend(query, n):
        calls.append(query)
        return [raw()]

    searcher, _ = make(backend)
    searcher.search("Python  Tutorials")
    searcher.search("python tutorials")
    assert len(calls) == 1


def test_cache_expires():
    calls = []
    searcher, clock = make(lambda q, n: calls.append(q) or [raw()], ttl=60)
    searcher.search("python tutorials")
    clock.now += 61
    searcher.search("python tutorials")
    assert len(calls) == 2


def test_empty_results_are_not_cached_so_a_retry_can_succeed():
    calls = []
    searcher, _ = make(lambda q, n: calls.append(q) or [])
    assert searcher.search("python tutorials") == []
    searcher.search("python tutorials")
    assert len(calls) == 2


def test_callers_cannot_change_the_cache_by_editing_results():
    searcher, _ = make(lambda q, n: [raw()])
    first = searcher.search("python tutorials")
    first[0]["title"] = "changed"
    assert searcher.search("python tutorials")[0]["title"] == "Title"


def test_calls_are_spaced_out():
    searcher, clock = make(lambda q, n: [raw()], min_interval=1.0)
    searcher.search("first query here")
    searcher.search("second query here")
    assert clock.slept and clock.slept[0] == pytest.approx(1.0)


def test_a_rate_limit_is_retried_once_and_then_succeeds():
    calls = []

    def flaky(query, n):
        calls.append(1)
        if len(calls) == 1:
            raise RatelimitException("202 Ratelimit")
        return [raw()]

    searcher, _ = make(flaky)
    assert len(searcher.search("python tutorials")) == 1
    assert len(calls) == 2


def test_a_permanent_error_is_not_retried_and_hides_its_details():
    calls = []

    def broken(query, n):
        calls.append(1)
        raise RuntimeError("secret internal detail")

    searcher, _ = make(broken)
    with pytest.raises(WebSearchError) as info:
        searcher.search("python tutorials")
    assert len(calls) == 1
    assert "secret" not in str(info.value)


def test_gives_up_after_the_last_attempt():
    calls = []

    def always_limited(query, n):
        calls.append(1)
        raise RatelimitException("slow down")

    searcher, _ = make(always_limited)
    with pytest.raises(WebSearchError, match="unavailable"):
        searcher.search("python tutorials")
    assert len(calls) == 2


def test_a_bad_query_is_a_value_error_not_a_search_error():
    searcher, _ = make(lambda q, n: pytest.fail("the backend must not be called"))
    with pytest.raises(ValueError):
        searcher.search("hi")
