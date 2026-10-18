import json
import os
from urllib.parse import quote

import httpx

API_URL = os.getenv("VERITY_API_URL", "http://127.0.0.1:8000")


class VerityError(Exception):
    """An error whose message is safe to show to the user."""


def _friendly(response):
    if response.status_code == 503:
        return "The AI service is busy. Please try again in a moment."
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, str):
        return detail
    if response.status_code == 422:
        return "That input could not be processed."
    return f"Something went wrong (error {response.status_code})."


def _request(method, path, client=None, **kwargs):
    own_client = client is None
    if own_client:
        client = httpx.Client(base_url=API_URL, timeout=60)
    try:
        response = client.request(method, path, **kwargs)
    except httpx.TransportError:
        raise VerityError("Cannot reach the Verity API. Is it running?") from None
    finally:
        if own_client:
            client.close()
    if response.status_code >= 400:
        raise VerityError(_friendly(response))
    return response.json()


def upload_pdf(name, data, client=None):
    files = {"file": (name, data, "application/pdf")}
    return _request("POST", "/upload", client=client, files=files)


def list_documents(client=None):
    return _request("GET", "/documents", client=client)["documents"]


def delete_document(name, client=None):
    return _request("DELETE", f"/documents/{quote(name, safe='')}", client=client)


def _ask_body(question, history, sources):
    body = {"question": question, "history": history or []}
    if sources:
        body["sources"] = sources
    return body


def ask(question, history=None, sources=None, client=None):
    body = _ask_body(question, history, sources)
    return _request("POST", "/ask", client=client, json=body)


def ask_stream(question, history=None, sources=None, client=None):
    """Yield events from /ask/stream as they arrive."""
    own_client = client is None
    if own_client:
        client = httpx.Client(base_url=API_URL, timeout=60)
    body = _ask_body(question, history, sources)
    try:
        with client.stream("POST", "/ask/stream", json=body) as response:
            if response.status_code >= 400:
                response.read()
                raise VerityError(_friendly(response))
            for line in response.iter_lines():
                if line.strip():
                    yield json.loads(line)
    except httpx.TransportError:
        raise VerityError("Cannot reach the Verity API. Is it running?") from None
    finally:
        if own_client:
            client.close()
