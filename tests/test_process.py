from unittest.mock import patch

import numpy as np

from app.sessions import SESSION_COOKIE, get_session


def _mock_scan(image):
    """Return a slightly different image to simulate processing."""
    return (image * 0.9).astype(np.uint8)


def test_process_returns_processed_image(client, sample_jpeg_file):
    resp = client.post("/upload", files=[sample_jpeg_file])
    sid = resp.cookies[SESSION_COOKIE]
    session = get_session(sid)
    page_id = session.pages[0].id

    with patch("app.routes.process.run_scan", side_effect=_mock_scan):
        resp = client.post(
            f"/process/{page_id}",
            cookies={SESSION_COOKIE: sid},
        )
    assert resp.status_code == 200
    assert "<img" in resp.text


def test_process_unknown_page_returns_404(client, sample_jpeg_file):
    resp = client.post("/upload", files=[sample_jpeg_file])
    sid = resp.cookies[SESSION_COOKIE]

    resp = client.post(
        "/process/nonexistent",
        cookies={SESSION_COOKIE: sid},
    )
    assert resp.status_code == 404


def test_process_updates_session_state(client, sample_jpeg_file):
    resp = client.post("/upload", files=[sample_jpeg_file])
    sid = resp.cookies[SESSION_COOKIE]
    session = get_session(sid)
    page_id = session.pages[0].id

    with patch("app.routes.process.run_scan", side_effect=_mock_scan):
        client.post(f"/process/{page_id}", cookies={SESSION_COOKIE: sid})

    page = session.pages[0]
    assert page.status == "done"
    assert page.processed is not None
    assert page.processed.exists()
