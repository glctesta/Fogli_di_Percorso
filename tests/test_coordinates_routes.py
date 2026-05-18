"""Test E2E della route /coordinates."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fdp_app.repos.coordinate_repo import ActiveCoordinate


@pytest.fixture
def mock_coord_repo():
    with patch("fdp_app.coordinates.routes.CoordinateRepo") as repo_cls:
        instance = MagicMock()
        instance.find_active.return_value = None
        repo_cls.return_value = instance
        yield instance


@pytest.fixture
def mock_routing():
    with patch("fdp_app.coordinates.routes.RoutingClient") as cls:
        instance = MagicMock()
        cls.return_value = instance
        yield instance


def _login(client, employee_hire_history_id=10):
    with client.session_transaction() as sess:
        sess["user_id"] = employee_hire_history_id
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = 5
        sess["function_code"] = 70


def test_get_coordinates_requires_login(client):
    response = client.get("/coordinates", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_get_coordinates_shows_no_active_point(client, mock_coord_repo, mock_routing):
    _login(client)
    mock_coord_repo.find_active.return_value = None

    response = client.get("/coordinates")

    assert response.status_code == 200
    assert b"Nessun punto attivo" in response.data
    assert b"id=\"map\"" in response.data  # contenitore mappa


def test_get_coordinates_shows_active_point(client, mock_coord_repo, mock_routing):
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(
        coordinate_id=100,
        label="Casa Mario",
        lat=45.4642,
        lon=9.19,
        road_km_to_workplace=12.345,
    )

    response = client.get("/coordinates")

    assert response.status_code == 200
    assert b"Casa Mario" in response.data
    assert b"45.4642" in response.data
    assert b"9.19" in response.data
    assert b"12.345" in response.data or b"12,345" in response.data


def test_post_create_inserts_when_no_active(client, mock_coord_repo, mock_routing):
    _login(client)
    mock_coord_repo.find_active.return_value = None
    mock_routing.road_km.return_value = 12.345
    mock_coord_repo.insert.return_value = 200

    response = client.post(
        "/coordinates",
        data={"lat": "45.4642", "lon": "9.19", "label": "Casa"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/coordinates" in response.headers["Location"]
    mock_coord_repo.insert.assert_called_once()
    kwargs = mock_coord_repo.insert.call_args.kwargs
    assert kwargs["employee_hire_history_id"] == 10
    assert kwargs["label"] == "Casa"
    assert kwargs["lat"] == 45.4642
    assert kwargs["lon"] == 9.19
    assert kwargs["road_km_to_workplace"] == 12.345


def test_post_create_rejects_when_active_exists(client, mock_coord_repo, mock_routing):
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(1, "x", 1.0, 2.0, 3.0)

    response = client.post(
        "/coordinates",
        data={"lat": "45.0", "lon": "9.0", "label": "y"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"esiste gi" in response.data.lower() or b"cancellare" in response.data.lower()
    mock_coord_repo.insert.assert_not_called()


def test_post_create_handles_routing_error(client, mock_coord_repo, mock_routing):
    from fdp_app.pathtracks.routing import RoutingError
    _login(client)
    mock_coord_repo.find_active.return_value = None
    mock_routing.road_km.side_effect = RoutingError("OSRM down")

    response = client.post(
        "/coordinates",
        data={"lat": "45.0", "lon": "9.0", "label": "y"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"mappe" in response.data.lower() or b"riprov" in response.data.lower()
    mock_coord_repo.insert.assert_not_called()


def test_post_create_validates_lat_lon_range(client, mock_coord_repo, mock_routing):
    _login(client)

    response = client.post(
        "/coordinates",
        data={"lat": "200", "lon": "9.0", "label": "y"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"non valid" in response.data.lower()
    mock_coord_repo.insert.assert_not_called()


def test_post_delete_soft_deletes_owned(client, mock_coord_repo):
    _login(client)
    mock_coord_repo.soft_delete.return_value = True

    response = client.post(
        "/coordinates/delete",
        data={"coordinate_id": "100"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/coordinates" in response.headers["Location"]
    mock_coord_repo.soft_delete.assert_called_once_with(
        coordinate_id=100, employee_hire_history_id=10
    )


def test_post_delete_not_owned_returns_404(client, mock_coord_repo):
    _login(client)
    mock_coord_repo.soft_delete.return_value = False  # nessuna riga aggiornata

    response = client.post(
        "/coordinates/delete",
        data={"coordinate_id": "999"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"non trovato" in response.data.lower() or b"non posseduto" in response.data.lower()
