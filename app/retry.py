import time

import httpx
from google.genai import errors


def is_temporary(exc):
    """Network drops, overloaded servers and rate limits can recover.
    A wrong key or a bad request will never recover, so it is not retried."""
    if isinstance(exc, httpx.TransportError | errors.ServerError):
        return True
    return isinstance(exc, errors.ClientError) and getattr(exc, "code", None) == 429


def with_retry(fn, attempts=3, delay=1.0, check=is_temporary):
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            if attempt == attempts or not check(exc):
                raise
            time.sleep(delay * attempt)
