from app.sessions import SESSION_COOKIE, get_session
from tests.conftest import upload_and_process_n


def test_delete_page(client, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 2)
    session = get_session(sid)
    first_id = session.pages[0].id
    original_path = session.pages[0].original

    resp = client.request(
        "DELETE",
        f"/pages/{first_id}",
        cookies={SESSION_COOKIE: sid},
    )
    assert resp.status_code == 200
    assert len(session.pages) == 1
    assert not original_path.exists()


def test_delete_unknown_page_returns_404(client, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 1)
    resp = client.request(
        "DELETE",
        "/pages/nonexistent",
        cookies={SESSION_COOKIE: sid},
    )
    assert resp.status_code == 404


def test_reorder_pages(client, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 3)
    session = get_session(sid)
    page_ids = [p.id for p in session.pages]
    new_order = [page_ids[2], page_ids[0], page_ids[1]]

    resp = client.put(
        "/pages/reorder",
        json={"order": new_order},
        cookies={SESSION_COOKIE: sid},
    )
    assert resp.status_code == 200
    assert [p.id for p in session.pages] == new_order


def test_reorder_with_invalid_ids_returns_422(client, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 1)

    resp = client.put(
        "/pages/reorder",
        json={"order": ["unknown1", "unknown2"]},
        cookies={SESSION_COOKIE: sid},
    )
    assert resp.status_code == 422
