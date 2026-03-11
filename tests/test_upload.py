from app.sessions import SESSION_COOKIE, get_session


def test_upload_accepts_jpeg(client, sample_jpeg_file):
    resp = client.post("/upload", files=[sample_jpeg_file])
    assert resp.status_code == 200
    assert "<img" in resp.text


def test_upload_rejects_non_image(client):
    files = [("file", ("notes.txt", b"hello world", "text/plain"))]
    resp = client.post("/upload", files=files)
    assert resp.status_code == 422


def test_upload_creates_session(client, sample_jpeg_file):
    resp = client.post("/upload", files=[sample_jpeg_file])
    assert SESSION_COOKIE in resp.cookies


def test_upload_stores_file_on_disk(client, sample_jpeg_file):
    resp = client.post("/upload", files=[sample_jpeg_file])
    sid = resp.cookies[SESSION_COOKIE]
    session = get_session(sid)
    assert session is not None
    assert len(session.pages) == 1
    assert session.pages[0].original.exists()


def test_upload_returns_processing_state(client, sample_jpeg_file):
    resp = client.post("/upload", files=[sample_jpeg_file])
    assert resp.status_code == 200
    sid = resp.cookies[SESSION_COOKIE]
    session = get_session(sid)
    page = session.pages[0]
    # Upload no longer processes inline — page stays pending
    assert page.status == "pending"
    # Response should contain spinner and auto-trigger for processing
    assert "animate-spin" in resp.text
    assert f'hx-post="/process/{page.id}"' in resp.text
    assert 'hx-trigger="load"' in resp.text
