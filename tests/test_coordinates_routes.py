"""Test E2E della route /coordinates."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fdp_app.repos.coordinate_repo import ActiveCoordinate


@pytest.fixture
def mock_coord_repo():
    with patch("fdp_app.coordinates.routes.CoordinateRepo") as repo_cls:
        instance = MagicMock()
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
