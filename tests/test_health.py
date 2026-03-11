def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_app_has_no_startup_errors(app):
    """Creating the app does not raise."""
    assert app is not None
