import re

from app.sessions import SESSION_COOKIE, get_session
from tests.conftest import upload_and_process_n


def test_assemble_single_page_pdf(client, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 1)
    resp = client.post("/assemble", cookies={SESSION_COOKIE: sid})
    assert resp.status_code == 200
    assert "application/pdf" in resp.headers["content-type"]
    assert resp.content[:4] == b"%PDF"


def test_assemble_multi_page_pdf(client, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 3)
    resp = client.post("/assemble", cookies={SESSION_COOKIE: sid})
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"
    page_count = len(re.findall(rb"/Type\s*/Page\b(?!s)", resp.content))
    assert page_count == 3


def test_assemble_empty_session_returns_422(client):
    resp = client.post("/assemble")
    assert resp.status_code == 422


def test_assemble_uses_session_order(client, sample_jpeg_file):
    sid = upload_and_process_n(client, sample_jpeg_file, 3)
    session = get_session(sid)
    page_ids = [p.id for p in session.pages]

    new_order = [page_ids[2], page_ids[0], page_ids[1]]
    client.put(
        "/pages/reorder",
        json={"order": new_order},
        cookies={SESSION_COOKIE: sid},
    )

    assert [p.id for p in session.pages] == new_order

    resp = client.post("/assemble", cookies={SESSION_COOKIE: sid})
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"
