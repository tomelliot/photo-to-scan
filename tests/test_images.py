from app.sessions import SESSION_COOKIE, get_session
from tests.conftest import upload_and_process_n


def test_get_original_image(client, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 1)
    session = get_session(sid)
    page_id = session.pages[0].id

    resp = client.get(
        f"/pages/{page_id}/image?type=original",
        cookies={SESSION_COOKIE: sid},
    )
    assert resp.status_code == 200
    assert "image/jpeg" in resp.headers["content-type"]


def test_get_processed_image(client, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 1)
    session = get_session(sid)
    page_id = session.pages[0].id

    resp = client.get(
        f"/pages/{page_id}/image?type=processed",
        cookies={SESSION_COOKIE: sid},
    )
    assert resp.status_code == 200


def test_get_unknown_page_returns_404(client, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 1)

    resp = client.get(
        "/pages/nonexistent/image",
        cookies={SESSION_COOKIE: sid},
    )
    assert resp.status_code == 404


def test_get_image_wrong_session_returns_404(client, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 1)
    session = get_session(sid)
    page_id = session.pages[0].id

    resp = client.get(
        f"/pages/{page_id}/image?type=original",
        cookies={SESSION_COOKIE: "wrong-session-id"},
    )
    assert resp.status_code == 404
