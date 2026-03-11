import io
from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app
from app.sessions import SESSION_COOKIE, clear_all_sessions, get_session


@pytest.fixture
def app():
    clear_all_sessions()
    return create_app()


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def sample_jpeg() -> bytes:
    """Create a minimal valid JPEG image in memory."""
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 80), color=(200, 180, 160))
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def sample_jpeg_file(sample_jpeg):
    """Return a tuple suitable for TestClient file upload."""
    return ("file", ("photo.jpg", sample_jpeg, "image/jpeg"))


def _mock_scan(image):
    """Simple mock that returns a slightly modified image."""
    return (image * 0.9).astype(np.uint8)


def upload_and_process_n(client, sample_jpeg_file, n):
    """Upload n images and process each. Returns session ID."""
    sid = None
    for _ in range(n):
        cookies = {SESSION_COOKIE: sid} if sid else {}
        resp = client.post("/upload", files=[sample_jpeg_file], cookies=cookies)
        sid = resp.cookies.get(SESSION_COOKIE, sid)

    # Now process each page
    session = get_session(sid)
    with patch("app.routes.process.run_scan", side_effect=_mock_scan):
        for page in session.pages:
            client.post(f"/process/{page.id}", cookies={SESSION_COOKIE: sid})

    return sid
