"""Web search for Verity's fallback. Free, no API key.

The text this module returns comes from strangers on the internet. Treat it as
data to read, never as instructions. The module cleans it, but the rules for
using it live in the answering code (Days 18 to 21).

Try it:  python -m app.websearch "how long is a cricket match"
"""
import logging
import re
import sys
import threading
import time
import unicodedata
from urllib.parse import urlparse

from app.retry import is_temporary, with_retry

logger = logging.getLogger("verity")

MAX_QUERY_CHARS = 200
MIN_QUERY_CHARS = 3
MAX_URL_CHARS = 2048
TEMPORARY_NAMES = {"RatelimitException", "TimeoutException"}


class WebSearchError(Exception):
    """Web search is unavailable. The message is safe to show to the user."""


def backend_error_is_temporary(exc):
    return type(exc).__name__ in TEMPORARY_NAMES or is_temporary(exc)


def ddgs_backend(query, max_results):
    """The real search. Imported here so tests and other code never need it."""
    from ddgs import DDGS

    with DDGS(timeout=10) as client:
        return list(client.text(query, max_results=max_results))


def tidy(value, limit):
    """Plain, single-line text of limited length. Invisible characters are
    removed because they can hide instructions from a human reader."""
    if not isinstance(value, str):
        return ""
    text = re.sub(r"\s+", " ", value)
    text = "".join(ch for ch in text if unicodedata.category(ch) not in ("Cc", "Cf"))
    return text.strip()[:limit].rstrip()


def clean_query(query):
    """A search query must be short and single-line. The length cap is also a
    safety net: pasted document text can never leave Verity by accident."""
    text = tidy(query, 10_000)
    if len(text) < MIN_QUERY_CHARS:
        raise ValueError("The search query is too short.")
    if len(text) > MAX_QUERY_CHARS:
        raise ValueError("The search query is too long.")
    return text


def clean_results(raw, max_results):
    seen = set()
    results = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("href") or item.get("url") or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            continue
        if parsed.username or parsed.password or len(url) > MAX_URL_CHARS:
            continue
        key = url.rstrip("/").lower()
        snippet = tidy(item.get("body") or item.get("snippet"), 400)
        if key in seen or not snippet:
            continue
        seen.add(key)
        domain = parsed.hostname.lower().removeprefix("www.")
        results.append({
            "title": tidy(item.get("title"), 160) or domain,
            "url": url,
            "snippet": snippet,
            "domain": domain,
        })
        if len(results) >= max_results:
            break
    return results


class WebSearcher:
    def __init__(self, backend=ddgs_backend, ttl=600, max_cache=128, min_interval=1.0,
                 clock=time.monotonic, sleep=time.sleep, retry_delay=1.0):
        self.backend = backend
        self.ttl = ttl
        self.max_cache = max_cache
        self.min_interval = min_interval
        self.clock = clock
        self.sleep = sleep
        self.retry_delay = retry_delay
        self._cache = {}
        self._last_call = float("-inf")
        self._lock = threading.Lock()

    def _cached(self, key):
        with self._lock:
            hit = self._cache.get(key)
            if hit and self.clock() - hit[0] < self.ttl:
                return [dict(r) for r in hit[1]]
            self._cache.pop(key, None)
        return None

    def _remember(self, key, results):
        with self._lock:
            if len(self._cache) >= self.max_cache:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = (self.clock(), results)

    def _throttle(self):
        with self._lock:
            wait = self.min_interval - (self.clock() - self._last_call)
            if wait > 0:
                self.sleep(wait)
            self._last_call = self.clock()

    def search(self, query, max_results=5):
        """Return up to max_results cleaned results. An empty list means the
        search worked and found nothing. WebSearchError means it is unavailable."""
        cleaned = clean_query(query)
        key = cleaned.lower()
        cached = self._cached(key)
        if cached is not None:
            return cached

        self._throttle()
        try:
            raw = with_retry(
                lambda: self.backend(cleaned, max_results),
                attempts=2,
                delay=self.retry_delay,
                check=backend_error_is_temporary,
            )
        except Exception as exc:  # noqa: BLE001 - any backend failure becomes one safe error
            logger.warning("Web search failed: %s", type(exc).__name__)
            raise WebSearchError("Web search is unavailable right now.") from None

        results = clean_results(raw, max_results)
        if results:
            self._remember(key, results)
        return [dict(r) for r in results]


_default = WebSearcher()


def search_web(query, max_results=5):
    return _default.search(query, max_results=max_results)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        found = search_web(" ".join(sys.argv[1:]))
    except (ValueError, WebSearchError) as error:
        sys.exit(str(error))
    if not found:
        print("No results.")
    for number, hit in enumerate(found, start=1):
        print(f"{number}. {hit['title']} ({hit['domain']})")
        print(f"   {hit['url']}")
        print(f"   {hit['snippet']}\n")
