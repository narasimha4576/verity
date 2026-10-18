from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

INDEX = Path("app/static/index.html")


def test_home_page_is_served():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Verity" in response.text


def test_page_never_inserts_text_as_html():
    # Answers come from an AI reading documents, so they must stay plain text.
    html = INDEX.read_text(encoding="utf-8")
    for dangerous in ("innerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert dangerous not in html


def test_page_uses_only_the_documented_api_routes():
    html = INDEX.read_text(encoding="utf-8")
    for route in ("/documents", "/upload", "/ask/stream"):
        assert route in html
