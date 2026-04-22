import json
from unittest.mock import patch, AsyncMock

import httpx

from app.sessions import SESSION_COOKIE, get_session, mark_session_submitted, SESSION_META_FILE
from tests.conftest import upload_and_process_n


def _mock_paperless(status=200):
    mock_response = httpx.Response(status, request=httpx.Request("POST", "http://paperless:8000/api/documents/post_document/"))
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def test_submit_calls_paperless_api(client, paperless_configured, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 1)
    mock_client = _mock_paperless()

    with patch("app.paperless.httpx.AsyncClient", return_value=mock_client):
        resp = client.post("/submit", cookies={SESSION_COOKIE: sid})

    assert resp.status_code == 200
    mock_client.post.assert_called_once()
    assert "/api/documents/post_document/" in mock_client.post.call_args[0][0]


def test_submit_archives_session(client, paperless_configured, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 1)
    session = get_session(sid)
    work_dir = session.work_dir
    mock_client = _mock_paperless()

    with patch("app.paperless.httpx.AsyncClient", return_value=mock_client):
        resp = client.post("/submit", cookies={SESSION_COOKIE: sid})

    # Session removed from memory
    assert get_session(sid) is None
    # Success response clears the page list via OOB swap
    assert "add-btn" in resp.text
    # Work dir still exists with metadata
    assert work_dir.exists()
    assert (work_dir / SESSION_META_FILE).exists()
    meta = json.loads((work_dir / SESSION_META_FILE).read_text())
    assert meta["reason"] == "submitted"
    assert meta["page_count"] == 1


def test_submit_without_paperless_config_shows_error(client, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 1)
    resp = client.post("/submit", cookies={SESSION_COOKIE: sid})
    assert resp.status_code == 200
    assert "Not configured" in resp.text
    assert "error-modal" in resp.text


def test_submit_paperless_error_shows_error_and_keeps_session(client, paperless_configured, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 1)
    mock_client = _mock_paperless(status=500)

    with patch("app.paperless.httpx.AsyncClient", return_value=mock_client):
        resp = client.post("/submit", cookies={SESSION_COOKIE: sid})

    assert resp.status_code == 200
    assert "Upload failed" in resp.text
    assert "error-modal" in resp.text
    assert get_session(sid) is not None


def test_double_submit_returns_error(client, paperless_configured, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 1)
    mock_client = _mock_paperless()

    # Mark as already submitted
    mark_session_submitted(sid)

    with patch("app.paperless.httpx.AsyncClient", return_value=mock_client):
        resp = client.post("/submit", cookies={SESSION_COOKIE: sid})

    assert resp.status_code == 200
    assert "Already submitted" in resp.text
    mock_client.post.assert_not_called()


def test_submit_forwards_selected_tags(client, paperless_configured, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 1)
    mock_client = _mock_paperless()

    with patch("app.paperless.httpx.AsyncClient", return_value=mock_client):
        resp = client.post(
            "/submit",
            data={"tags": ["3", "7"]},
            cookies={SESSION_COOKIE: sid},
        )

    assert resp.status_code == 200
    mock_client.post.assert_called_once()
    sent_data = mock_client.post.call_args.kwargs["data"]
    # httpx accepts a list of tuples for repeated form fields
    if isinstance(sent_data, list):
        tag_values = [v for k, v in sent_data if k == "tags"]
    else:
        tag_values = sent_data.get("tags") if not isinstance(sent_data.get("tags"), str) else [sent_data["tags"]]
    assert sorted(tag_values) == ["3", "7"]


def test_submit_without_tags_sends_no_tag_field(client, paperless_configured, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 1)
    mock_client = _mock_paperless()

    with patch("app.paperless.httpx.AsyncClient", return_value=mock_client):
        resp = client.post("/submit", cookies={SESSION_COOKIE: sid})

    assert resp.status_code == 200
    sent_data = mock_client.post.call_args.kwargs.get("data")
    if sent_data is None:
        return
    if isinstance(sent_data, list):
        assert not any(k == "tags" for k, _ in sent_data)
    else:
        assert "tags" not in sent_data


def test_submit_writes_session_meta(client, paperless_configured, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 1)
    session = get_session(sid)
    work_dir = session.work_dir
    mock_client = _mock_paperless()

    with patch("app.paperless.httpx.AsyncClient", return_value=mock_client):
        resp = client.post("/submit", cookies={SESSION_COOKIE: sid})

    assert resp.status_code == 200
    assert (work_dir / SESSION_META_FILE).exists()
    meta = json.loads((work_dir / SESSION_META_FILE).read_text())
    assert meta["reason"] == "submitted"
    assert "archived_at" in meta
    assert "created_at" in meta
    assert meta["page_count"] == 1
