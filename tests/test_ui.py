from unittest.mock import patch, AsyncMock

import httpx

from app.sessions import SESSION_COOKIE, get_session
from tests.conftest import upload_and_process_n


def test_index_has_capture_input(client):
    resp = client.get("/")
    assert 'capture="environment"' in resp.text


def test_index_has_submit_button(client):
    resp = client.get("/")
    assert "Upload document" in resp.text


def test_index_has_sortable(client):
    resp = client.get("/")
    assert "Sortable" in resp.text or "sortablejs" in resp.text


def test_full_flow_integration(client, sample_jpeg_file):
    # Upload 2 images and process them
    sid = upload_and_process_n(client, sample_jpeg_file, 2)
    session = get_session(sid)
    assert len(session.pages) == 2

    # Delete first page
    first_id = session.pages[0].id
    resp = client.request("DELETE", f"/pages/{first_id}", cookies={SESSION_COOKIE: sid})
    assert resp.status_code == 200
    assert len(session.pages) == 1

    # Submit to paperless (mocked)
    mock_response = httpx.Response(200, request=httpx.Request("POST", "http://paperless:8000/api/documents/post_document/"))
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    from app.config import Settings
    settings = Settings(paperless_url="http://paperless:8000", paperless_token="tok", work_dir="/tmp/paperless-feeder-sessions")

    with (
        patch("app.routes.submit.get_settings", return_value=settings),
        patch("httpx.AsyncClient", return_value=mock_client),
    ):
        resp = client.post("/submit", cookies={SESSION_COOKIE: sid})

    assert resp.status_code == 200
    mock_client.post.assert_called_once()
