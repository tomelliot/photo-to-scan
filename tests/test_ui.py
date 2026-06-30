from unittest.mock import patch, AsyncMock

import httpx

from app.sessions import SESSION_COOKIE, get_session
from tests.conftest import upload_and_process_n


def test_index_has_file_input(client):
    resp = client.get("/")
    # The add-page input accepts images...
    assert 'accept="image/*"' in resp.text
    # ...but does not force the camera, so the user can pick camera or files.
    assert 'capture=' not in resp.text


def test_index_has_submit_button(client):
    resp = client.get("/")
    assert "Upload document" in resp.text


def test_index_has_sortable(client):
    resp = client.get("/")
    assert "Sortable" in resp.text or "sortablejs" in resp.text


def test_index_has_label_selector_button(client):
    resp = client.get("/")
    # Button exists with a stable id
    assert 'id="label-selector-btn"' in resp.text


def test_label_selector_starts_disabled(client):
    """The label selector should be disabled until tags load in the background."""
    resp = client.get("/")
    # Alpine should bind disabled to a state that starts true (tags not yet loaded)
    assert ":disabled" in resp.text
    # Initial Alpine state declares that tags are loading / unavailable
    assert "tagsLoaded" in resp.text


def test_label_selector_uses_lucide_icon(client):
    resp = client.get("/")
    # Use a Lucide icon (tag/tags) — referenced by the lucide CDN script
    assert "lucide" in resp.text.lower()


def test_index_loads_alpine_component_module(client):
    """The UI's Alpine state lives in /static/app.js (STANDARDS rule 5).
    Verify the template references it and the file is served."""
    resp = client.get("/")
    assert 'src="/static/app.js"' in resp.text

    js_resp = client.get("/static/app.js")
    assert js_resp.status_code == 200
    # The behaviour under test — loading tags in the background — is
    # exercised end-to-end by tests/test_browser.py; string-match tests on
    # the JS body would re-create the false-confidence problem from 74fcbd6.
    assert "documentUploader" in js_resp.text


def test_label_selector_popover_has_search(client):
    resp = client.get("/")
    # Popover container with search input
    assert 'id="label-popover"' in resp.text
    assert 'id="label-search"' in resp.text


# The real "does submit include selected tags?" check lives in
# tests/test_browser.py::test_submit_with_tag_does_not_throw_js_error.
# A string-match assertion here would pass even if hx-vals evaluated
# `selectedTags` in global scope and crashed — see commit 74fcbd6.


def test_label_selector_to_left_of_submit(client):
    """The label selector and submit button should share a row, selector on the left."""
    resp = client.get("/")
    text = resp.text
    selector_idx = text.find('id="label-selector-btn"')
    submit_idx = text.find('id="submit-btn"')
    assert selector_idx != -1 and submit_idx != -1
    assert selector_idx < submit_idx


def test_full_flow_integration(client, paperless_configured, sample_jpeg_file):
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

    with patch("app.paperless.httpx.AsyncClient", return_value=mock_client):
        resp = client.post("/submit", cookies={SESSION_COOKIE: sid})

    assert resp.status_code == 200
    mock_client.post.assert_called_once()
