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


def test_process_scan_returns_none_marks_page_failed(client, sample_jpeg_file):
    """When the scan pipeline can't detect a document it returns None.
    The route must flag the page as failed — not silently mark it 'done'
    with the original image (the pre-refactor behaviour that hid failures)."""
    resp = client.post("/upload", files=[sample_jpeg_file])
    sid = resp.cookies[SESSION_COOKIE]
    session = get_session(sid)
    page_id = session.pages[0].id

    with patch("app.routes.process.run_scan", return_value=None):
        resp = client.post(f"/process/{page_id}", cookies={SESSION_COOKIE: sid})

    assert resp.status_code == 200
    assert "Could not detect document" in resp.text

    page = session.pages[0]
    assert page.status == "failed"
    assert page.processed is None


def test_process_scan_raises_is_treated_as_failure(client, sample_jpeg_file):
    """An unexpected exception during scan is logged and surfaced as a
    detection failure to the user, not a 500. Until a central exception
    handler lands (STANDARDS.md rule 7), this is the best the route can do."""
    resp = client.post("/upload", files=[sample_jpeg_file])
    sid = resp.cookies[SESSION_COOKIE]
    session = get_session(sid)
    page_id = session.pages[0].id

    with patch("app.routes.process.run_scan", side_effect=RuntimeError("boom")):
        resp = client.post(f"/process/{page_id}", cookies={SESSION_COOKIE: sid})

    assert resp.status_code == 200
    assert "Could not detect document" in resp.text
    assert session.pages[0].status == "failed"
