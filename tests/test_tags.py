"""Tests for /tags endpoint that proxies Paperless tags."""

from unittest.mock import patch, AsyncMock

import httpx


def _settings_with_paperless(**overrides):
    defaults = {
        "paperless_url": "http://paperless:8000",
        "paperless_token": "test-token",
        "work_dir": "/tmp/paperless-feeder-sessions",
    }
    defaults.update(overrides)
    from app.config import Settings
    return Settings(**defaults)


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


def test_tags_returns_paperless_tags(client):
    results = [
        {"id": 1, "name": "Invoice", "slug": "invoice", "colour": 1},
        {"id": 2, "name": "Receipt", "slug": "receipt", "colour": 2},
    ]
    mock_client = _mock_async_client(_mock_paperless_tags_response(results))

    with (
        patch("app.routes.tags.get_settings", return_value=_settings_with_paperless()),
        patch("httpx.AsyncClient", return_value=mock_client),
    ):
        resp = client.get("/tags")

    assert resp.status_code == 200
    data = resp.json()
    assert data == [
        {"id": 1, "name": "Invoice"},
        {"id": 2, "name": "Receipt"},
    ]


def test_tags_handles_pagination(client):
    page1 = [{"id": 1, "name": "Invoice", "slug": "invoice", "colour": 1}]
    page2 = [{"id": 2, "name": "Receipt", "slug": "receipt", "colour": 2}]
    mock_client = _mock_async_client(
        _mock_paperless_tags_response(page1, next_page="http://paperless:8000/api/tags/?page=2"),
        _mock_paperless_tags_response(page2),
    )

    with (
        patch("app.routes.tags.get_settings", return_value=_settings_with_paperless()),
        patch("httpx.AsyncClient", return_value=mock_client),
    ):
        resp = client.get("/tags")

    assert resp.status_code == 200
    data = resp.json()
    assert [t["name"] for t in data] == ["Invoice", "Receipt"]


def test_tags_without_paperless_config_returns_503(client):
    resp = client.get("/tags")
    assert resp.status_code == 503


def test_tags_paperless_error_returns_502(client):
    error_resp = httpx.Response(500, request=httpx.Request("GET", "http://paperless:8000/api/tags/"))
    mock_client = _mock_async_client(error_resp)

    with (
        patch("app.routes.tags.get_settings", return_value=_settings_with_paperless()),
        patch("httpx.AsyncClient", return_value=mock_client),
    ):
        resp = client.get("/tags")

    assert resp.status_code == 502


def test_tags_connection_error_returns_502(client):
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.ConnectError("nope")
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.routes.tags.get_settings", return_value=_settings_with_paperless()),
        patch("httpx.AsyncClient", return_value=mock_client),
    ):
        resp = client.get("/tags")

    assert resp.status_code == 502
