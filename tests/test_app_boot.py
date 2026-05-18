def test_app_can_be_created(app):
    """L'app Flask si avvia senza errori e ha config TESTING attivo."""
    assert app is not None
    assert app.config["TESTING"] is True


def test_unknown_route_returns_404(client):
    response = client.get("/this-route-does-not-exist")
    assert response.status_code == 404
