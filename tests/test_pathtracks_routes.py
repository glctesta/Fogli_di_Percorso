"""Test E2E delle route /pathtracks/*."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from freezegun import freeze_time


@pytest.fixture
def mock_coord_repo():
    with patch("fdp_app.pathtracks.routes.CoordinateRepo") as cls:
        instance = MagicMock()
        instance.find_active.return_value = None
        cls.return_value = instance
        yield instance


@pytest.fixture
def mock_rate_repo():
    with patch("fdp_app.pathtracks.routes.RateRepo") as cls:
        instance = MagicMock()
        cls.return_value = instance
        yield instance


@pytest.fixture
def mock_pathtrack_repo():
    with patch("fdp_app.pathtracks.routes.PathTrackRepo") as cls:
        instance = MagicMock()
        instance.find_active_for_month.return_value = None
        instance.list_for_employee.return_value = []
        cls.return_value = instance
        yield instance


@pytest.fixture
def mock_doc_repo():
    with patch("fdp_app.pathtracks.routes.PathTrackDocRepo") as cls:
        instance = MagicMock()
        cls.return_value = instance
        yield instance


@pytest.fixture
def mock_registry_repo():
    with patch("fdp_app.pathtracks.routes.RegistryRepo") as cls:
        instance = MagicMock()
        cls.return_value = instance
        yield instance


def _login(client, eh_id=10):
    with client.session_transaction() as sess:
        sess["user_id"] = eh_id
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = 5
        sess["function_code"] = 70


def test_new_requires_login(client):
    response = client.get("/pathtracks/new", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


@freeze_time("2026-05-03 10:00:00+02:00")
def test_new_redirects_to_coordinates_when_no_active_coordinate(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo
):
    _login(client)
    mock_coord_repo.find_active.return_value = None

    response = client.get("/pathtracks/new", follow_redirects=False)
    assert response.status_code == 302
    assert "/coordinates" in response.headers["Location"]


@freeze_time("2026-05-03 10:00:00+02:00")
def test_new_shows_form_when_in_deadline_window(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo
):
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    from fdp_app.repos.rate_repo import Rate
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(
        coordinate_id=99, label="Casa", lat=45.0, lon=9.0, road_km_to_workplace=10.5,
    )
    mock_rate_repo.find_for_date.return_value = Rate(
        rate_id=3, avg_consumption_km_l=15.0, avg_fuel_price_eur_l=1.7,
    )
    mock_pathtrack_repo.find_active_for_month.return_value = None

    response = client.get("/pathtracks/new")
    assert response.status_code == 200
    assert b"Dichiarazione mensile" in response.data
    assert b"10.5" in response.data or b"10,5" in response.data


@freeze_time("2026-05-06 00:00:01+02:00")
def test_new_blocks_when_deadline_passed(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo
):
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 10.0)

    response = client.get("/pathtracks/new", follow_redirects=True)
    assert response.status_code == 200
    assert b"chius" in response.data.lower() or b"scadut" in response.data.lower()
