import httpx
import pytest

from app.client import VerityError, ask, upload_pdf


def make_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")


def test_ask_returns_the_api_json():
    def handler(request):
        assert request.url.path == "/ask"
        return httpx.Response(
            200, json={"status": "answered", "answer": "30 days", "sources": []}
        )

    assert ask("waiting period?", client=make_client(handler))["answer"] == "30 days"


def test_upload_sends_the_file():
    def handler(request):
        assert request.url.path == "/upload"
        assert b"policy.pdf" in request.content
        return httpx.Response(200, json={"filename": "policy.pdf", "chunks": 6})

    result = upload_pdf("policy.pdf", b"%PDF-1.4", client=make_client(handler))
    assert result["chunks"] == 6


def test_busy_ai_gives_a_friendly_message():
    def handler(request):
        return httpx.Response(503, json={"detail": "internal wording"})

    with pytest.raises(VerityError, match="busy"):
        ask("x", client=make_client(handler))


def test_api_error_detail_is_shown_to_the_user():
    def handler(request):
        return httpx.Response(400, json={"detail": "Only PDF files are accepted."})

    with pytest.raises(VerityError, match="Only PDF files"):
        upload_pdf("a.txt", b"hi", client=make_client(handler))


def test_api_down_gives_a_clear_message():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(VerityError, match="Cannot reach"):
        ask("x", client=make_client(handler))


def test_validation_error_does_not_leak_technical_details():
    def handler(request):
        return httpx.Response(422, json={"detail": [{"msg": "string too short"}]})

    with pytest.raises(VerityError, match="could not be processed"):
        ask("", client=make_client(handler))
