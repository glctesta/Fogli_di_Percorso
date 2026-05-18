"""Test dashboard."""


def test_dashboard_redirects_anonymous_to_login(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_dashboard_renders_for_logged_user(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = 7
        sess["function_code"] = 65

    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"Rossi Mario" in response.data
    assert b"Benvenuto" in response.data


def test_root_redirects_to_dashboard(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]


def test_dashboard_card_links_to_coordinates(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = 7
        sess["function_code"] = 65

    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"/coordinates" in response.data
    # La card "Punto di partenza" non e' piu' disabled per il Piano 2
    assert b"Disponibile nel Piano 2" not in response.data
