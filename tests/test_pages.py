def test_index_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_index_includes_htmx(client):
    resp = client.get("/")
    assert "/static/vendor/htmx.min.js" in resp.text


def test_index_includes_alpine(client):
    resp = client.get("/")
    assert "/static/vendor/alpine.min.js" in resp.text
