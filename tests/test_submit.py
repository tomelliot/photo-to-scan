from unittest.mock import patch, AsyncMock

import httpx

from app.sessions import SESSION_COOKIE, get_session
from tests.conftest import upload_and_process_n


def _settings_with_paperless(**overrides):
    defaults = {
        "paperless_url": "http://paperless:8000",
        "paperless_token": "test-token",
        "work_dir": "/tmp/paperless-feeder-sessions",
    }
    defaults.update(overrides)
    from app.config import Settings
    return Settings(**defaults)


def _mock_paperless(status=200):
    mock_response = httpx.Response(status, request=httpx.Request("POST", "http://paperless:8000/api/documents/post_document/"))
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def test_submit_calls_paperless_api(client, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 1)
    mock_client = _mock_paperless()

    with (
        patch("app.routes.submit.get_settings", return_value=_settings_with_paperless()),
        patch("httpx.AsyncClient", return_value=mock_client),
    ):
        resp = client.post("/submit", cookies={SESSION_COOKIE: sid})

    assert resp.status_code == 200
    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    assert "paperless:8000" in call_kwargs[0][0]
    assert "Token test-token" in call_kwargs[1]["headers"]["Authorization"]


def test_submit_clears_session(client, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 1)
    mock_client = _mock_paperless()

    with (
        patch("app.routes.submit.get_settings", return_value=_settings_with_paperless()),
        patch("httpx.AsyncClient", return_value=mock_client),
    ):
        client.post("/submit", cookies={SESSION_COOKIE: sid})

    assert get_session(sid) is None


def test_submit_without_paperless_config_returns_503(client, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 1)
    resp = client.post("/submit", cookies={SESSION_COOKIE: sid})
    assert resp.status_code == 503


def test_submit_paperless_error_returns_502(client, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 1)
    mock_client = _mock_paperless(status=500)

    with (
        patch("app.routes.submit.get_settings", return_value=_settings_with_paperless()),
        patch("httpx.AsyncClient", return_value=mock_client),
    ):
        resp = client.post("/submit", cookies={SESSION_COOKIE: sid})

    assert resp.status_code == 502
    assert get_session(sid) is not None
