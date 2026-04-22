"""Unit tests for the Paperless client.

These tests use `httpx.MockTransport` so the real httpx encoder runs —
bugs like the `data=[(k,v),...]` sync-stream regression in httpx 0.28 only
surface when encoding is exercised. Tests that patch `httpx.AsyncClient`
wholesale cannot catch that class of bug.

Test bodies are plain `async def` coroutines driven by `_run(...)`
from sync test functions. This avoids pytest-asyncio, which in our env
conflicts with pytest-playwright's event-loop bookkeeping when tests
from both plugins run in the same session.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.config import Settings
from app.paperless import (
    PaperlessClient,
    PaperlessNotConfigured,
    Tag,
    paperless_client,
)


def _run(coro):
    """Run an async body in a fresh event loop on a fresh thread.

    pytest-playwright leaves a running asyncio loop in the main thread even
    after its tests finish, which makes `asyncio.run()` / `loop.run_until_complete()`
    unusable from sync test bodies for the rest of the session. Running on
    a dedicated thread gives us a clean slate.
    """
    import threading

    result: list = [None]
    error: list = [None]

    def runner() -> None:
        loop = asyncio.new_event_loop()
        try:
            result[0] = loop.run_until_complete(coro)
        except BaseException as exc:  # re-raise in the calling thread
            error[0] = exc
        finally:
            loop.close()

    t = threading.Thread(target=runner)
    t.start()
    t.join()
    if error[0] is not None:
        raise error[0]
    return result[0]


def _client_with_handler(handler):
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport, base_url="http://paperless:8000")


def test_post_document_sends_pdf_bytes():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=42)

    async def body():
        async with _client_with_handler(handler) as transport:
            client = PaperlessClient(transport)
            await client.post_document(b"%PDF-1.4\nfake", [], "doc.pdf")

    _run(body())

    req = captured[0]
    assert req.method == "POST"
    assert req.url.path == "/api/documents/post_document/"
    assert b"%PDF-1.4\nfake" in req.content
    assert b'name="document"' in req.content


def test_post_document_sends_multiple_tags_as_repeated_form_field():
    """The regression for the httpx-0.28 list-of-tuples/AsyncClient bug: the
    wire format must carry repeated `tags` fields and encoding must not
    raise RuntimeError. Any test that patches AsyncClient wholesale will
    miss this — that's why these tests use MockTransport."""
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=42)

    async def body():
        async with _client_with_handler(handler) as transport:
            client = PaperlessClient(transport)
            await client.post_document(b"%PDF-1.4\nfake", [3, 7], "doc.pdf")

    _run(body())

    body_bytes = captured[0].content
    tag_parts = body_bytes.count(b'name="tags"')
    assert tag_parts == 2, f"expected 2 'tags' parts, got {tag_parts}"
    assert b"\r\n\r\n3\r\n" in body_bytes
    assert b"\r\n\r\n7\r\n" in body_bytes


def test_post_document_raises_on_non_2xx():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="nope")

    async def body():
        async with _client_with_handler(handler) as transport:
            client = PaperlessClient(transport)
            await client.post_document(b"pdf", [], "doc.pdf")

    with pytest.raises(httpx.HTTPStatusError):
        _run(body())


def test_list_tags_follows_pagination():
    pages = {
        "page_size=200": {
            "results": [{"id": 1, "name": "A"}],
            "next": "http://paperless:8000/api/tags/?page=2",
        },
        "page=2": {
            "results": [{"id": 2, "name": "B"}],
            "next": None,
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=pages[request.url.query.decode()])

    async def body():
        async with _client_with_handler(handler) as transport:
            client = PaperlessClient(transport)
            return await client.list_tags()

    tags = _run(body())
    assert tags == [Tag(id=1, name="A"), Tag(id=2, name="B")]


def test_paperless_client_raises_when_not_configured():
    settings = Settings(paperless_url="", paperless_token="")

    async def body():
        async with paperless_client(settings):
            pass

    with pytest.raises(PaperlessNotConfigured):
        _run(body())


def test_paperless_client_raises_when_url_only():
    settings = Settings(paperless_url="http://paperless:8000", paperless_token="")

    async def body():
        async with paperless_client(settings):
            pass

    with pytest.raises(PaperlessNotConfigured):
        _run(body())
