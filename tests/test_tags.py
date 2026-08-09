"""Tests for /tags endpoint that proxies Paperless tags."""

from unittest.mock import patch, AsyncMock

import httpx


def _mock_paperless_tags_response(results, next_page=None):
    body = {"count": len(results), "next": next_page, "previous": None, "results": results}
    return httpx.Response(200, json=body, request=httpx.Request("GET", "http://paperless:8000/api/tags/"))


def _mock_async_client(*responses):
    """Build an AsyncClient mock whose .get() returns the given responses in order."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = list(responses)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def test_tags_returns_paperless_tags(client, paperless_configured):
    results = [
        {"id": 1, "name": "Invoice", "slug": "invoice", "colour": 1},
        {"id": 2, "name": "Receipt", "slug": "receipt", "colour": 2},
    ]
    mock_client = _mock_async_client(_mock_paperless_tags_response(results))

    with patch("app.paperless.httpx.AsyncClient", return_value=mock_client):
        resp = client.get("/tags")

    assert resp.status_code == 200
    data = resp.json()
    assert data == [
        {"id": 1, "name": "Invoice"},
        {"id": 2, "name": "Receipt"},
    ]


def test_tags_handles_pagination(client, paperless_configured):
    page1 = [{"id": 1, "name": "Invoice", "slug": "invoice", "colour": 1}]
    page2 = [{"id": 2, "name": "Receipt", "slug": "receipt", "colour": 2}]
    mock_client = _mock_async_client(
        _mock_paperless_tags_response(page1, next_page="http://paperless:8000/api/tags/?page=2"),
        _mock_paperless_tags_response(page2),
    )

    with patch("app.paperless.httpx.AsyncClient", return_value=mock_client):
        resp = client.get("/tags")

    assert resp.status_code == 200
    data = resp.json()
    assert [t["name"] for t in data] == ["Invoice", "Receipt"]


def test_tags_sorted_by_document_count_descending(client, paperless_configured):
    results = [
        {"id": 1, "name": "Invoice", "slug": "invoice", "colour": 1, "document_count": 3},
        {"id": 2, "name": "Receipt", "slug": "receipt", "colour": 2, "document_count": 41},
        {"id": 3, "name": "Warranty", "slug": "warranty", "colour": 3, "document_count": 0},
    ]
    mock_client = _mock_async_client(_mock_paperless_tags_response(results))

    with patch("app.paperless.httpx.AsyncClient", return_value=mock_client):
        resp = client.get("/tags")

    assert resp.status_code == 200
    assert [t["name"] for t in resp.json()] == ["Receipt", "Invoice", "Warranty"]


def test_tags_sorted_by_name_when_counts_tie(client, paperless_configured):
    """Ties break on name so the picker order doesn't shuffle between requests."""
    results = [
        {"id": 1, "name": "receipt", "slug": "receipt", "colour": 1, "document_count": 5},
        {"id": 2, "name": "Invoice", "slug": "invoice", "colour": 2, "document_count": 5},
        {"id": 3, "name": "Bank", "slug": "bank", "colour": 3, "document_count": 5},
    ]
    mock_client = _mock_async_client(_mock_paperless_tags_response(results))

    with patch("app.paperless.httpx.AsyncClient", return_value=mock_client):
        resp = client.get("/tags")

    assert resp.status_code == 200
    assert [t["name"] for t in resp.json()] == ["Bank", "Invoice", "receipt"]


def test_tags_sorts_across_pages(client, paperless_configured):
    """The most-used tag on page 2 must still come first overall."""
    page1 = [{"id": 1, "name": "Invoice", "slug": "invoice", "colour": 1, "document_count": 2}]
    page2 = [{"id": 2, "name": "Receipt", "slug": "receipt", "colour": 2, "document_count": 9}]
    mock_client = _mock_async_client(
        _mock_paperless_tags_response(page1, next_page="http://paperless:8000/api/tags/?page=2"),
        _mock_paperless_tags_response(page2),
    )

    with patch("app.paperless.httpx.AsyncClient", return_value=mock_client):
        resp = client.get("/tags")

    assert resp.status_code == 200
    assert [t["name"] for t in resp.json()] == ["Receipt", "Invoice"]


def test_tags_without_document_count_falls_back_to_name_order(client, paperless_configured):
    """Older Paperless versions omit `document_count`; don't 500 on them."""
    results = [
        {"id": 1, "name": "Receipt", "slug": "receipt", "colour": 1},
        {"id": 2, "name": "Invoice", "slug": "invoice", "colour": 2},
    ]
    mock_client = _mock_async_client(_mock_paperless_tags_response(results))

    with patch("app.paperless.httpx.AsyncClient", return_value=mock_client):
        resp = client.get("/tags")

    assert resp.status_code == 200
    assert [t["name"] for t in resp.json()] == ["Invoice", "Receipt"]


def test_tags_without_paperless_config_returns_503(client):
    resp = client.get("/tags")
    assert resp.status_code == 503


def test_tags_paperless_error_returns_502(client, paperless_configured):
    error_resp = httpx.Response(500, request=httpx.Request("GET", "http://paperless:8000/api/tags/"))
    mock_client = _mock_async_client(error_resp)

    with patch("app.paperless.httpx.AsyncClient", return_value=mock_client):
        resp = client.get("/tags")

    assert resp.status_code == 502


def test_tags_connection_error_returns_502(client, paperless_configured):
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.ConnectError("nope")
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.paperless.httpx.AsyncClient", return_value=mock_client):
        resp = client.get("/tags")

    assert resp.status_code == 502
