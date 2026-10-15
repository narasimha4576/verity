import httpx
import pytest

from app.retry import is_temporary, with_retry


def test_network_error_is_temporary_but_value_error_is_not():
    assert is_temporary(httpx.ConnectError("dropped"))
    assert not is_temporary(ValueError("bad input"))


def test_temporary_error_is_retried_until_success():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise httpx.ConnectError("dropped")
        return "ok"

    assert with_retry(flaky, attempts=3, delay=0) == "ok"
    assert len(calls) == 3


def test_permanent_error_is_not_retried():
    calls = []

    def broken():
        calls.append(1)
        raise ValueError("wrong key")

    with pytest.raises(ValueError):
        with_retry(broken, attempts=3, delay=0)
    assert len(calls) == 1


def test_gives_up_after_the_last_attempt():
    calls = []

    def always_down():
        calls.append(1)
        raise httpx.ConnectError("dropped")

    with pytest.raises(httpx.ConnectError):
        with_retry(always_down, attempts=3, delay=0)
    assert len(calls) == 3
