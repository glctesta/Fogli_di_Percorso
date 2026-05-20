"""Test E2E della modalita' ?on_behalf_of=<id> su /coordinates e /pathtracks."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fdp_app.repos.coordinate_repo import ActiveCoordinate
from fdp_app.repos.employee_repo import RepresentableEmployee


@pytest.fixture
def mock_employee_repo_for_resolver():
    """Patch EmployeeRepo dove viene importato dai resolve helpers."""
    with patch("fdp_app.admin.helpers.EmployeeRepo") as cls:
        instance = MagicMock()
        instance.find_representable_for.return_value = [
            RepresentableEmployee(101, "Bianchi", "Luigi", 42, 50),
        ]
        cls.return_value = instance
        yield instance


@pytest.fixture
def mock_coord_repo():
    with patch("fdp_app.coordinates.routes.CoordinateRepo") as cls:
        instance = MagicMock()
        instance.find_active.return_value = None
        cls.return_value = instance
        yield instance


def _login_admin(client, eh_id=10, sub_cdc_id=42, fc=70):
    with client.session_transaction() as sess:
        sess["user_id"] = eh_id
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = sub_cdc_id
        sess["function_code"] = fc


# ---- /coordinates?on_behalf_of=<id> -------------------------------------

def test_coordinates_on_behalf_of_uses_target_employee(
    client, mock_employee_repo_for_resolver, mock_coord_repo
):
    _login_admin(client, eh_id=10, sub_cdc_id=42)
    mock_coord_repo.find_active.return_value = None

    response = client.get("/coordinates?on_behalf_of=101")
    assert response.status_code == 200
    # find_active dovrebbe essere chiamato con target_id=101, non con 10
    mock_coord_repo.find_active.assert_called_with(101)
    assert b"per conto di Bianchi Luigi" in response.data


def test_coordinates_on_behalf_of_unauthorized_returns_403(
    client, mock_employee_repo_for_resolver, mock_coord_repo
):
    _login_admin(client, eh_id=10, sub_cdc_id=42)
    # 999 not in the representable list -> 403
    response = client.get("/coordinates?on_behalf_of=999")
    assert response.status_code == 403


def test_coordinates_on_behalf_of_invalid_id_returns_400(
    client, mock_employee_repo_for_resolver, mock_coord_repo
):
    _login_admin(client)
    response = client.get("/coordinates?on_behalf_of=notanint")
    assert response.status_code == 400


def test_coordinates_self_when_no_on_behalf_of(
    client, mock_employee_repo_for_resolver, mock_coord_repo
):
    """Senza ?on_behalf_of=, find_active e' chiamato con session.user_id."""
    _login_admin(client, eh_id=10)
    response = client.get("/coordinates")
    assert response.status_code == 200
    mock_coord_repo.find_active.assert_called_with(10)
    # No banner
    assert b"per conto di" not in response.data


# ---- /pathtracks/new?on_behalf_of=<id> ----------------------------------

@pytest.fixture
def mock_pt_repos_for_pathtracks():
    """Patch all the repos imported by pathtracks/routes.py."""
    patches = []
    instances = {}
    for name in ["CoordinateRepo", "RateRepo", "RegistryRepo", "PathTrackRepo", "PathTrackDocRepo"]:
        p = patch(f"fdp_app.pathtracks.routes.{name}")
        mock_cls = p.start()
        patches.append(p)
        instances[name] = MagicMock()
        mock_cls.return_value = instances[name]
    instances["CoordinateRepo"].find_active.return_value = None
    instances["PathTrackRepo"].find_active_for_month.return_value = None
    yield instances
    for p in patches:
        p.stop()


from freezegun import freeze_time


@freeze_time("2026-05-15 10:00:00+02:00")
def test_pathtracks_new_on_behalf_of_shows_banner_and_uses_target(
    client, mock_employee_repo_for_resolver, mock_pt_repos_for_pathtracks
):
    from fdp_app.repos.rate_repo import Rate
    _login_admin(client, eh_id=10, sub_cdc_id=42)
    mock_pt_repos_for_pathtracks["CoordinateRepo"].find_active.return_value = ActiveCoordinate(
        99, "Casa", 45.0, 9.0, 10.0,
    )
    mock_pt_repos_for_pathtracks["RateRepo"].find_for_date.return_value = Rate(3, 15.0, 1.7)

    response = client.get("/pathtracks/new?on_behalf_of=101")
    assert response.status_code == 200
    # Should look up coord for target 101, not user 10
    mock_pt_repos_for_pathtracks["CoordinateRepo"].find_active.assert_called_with(101)
    assert b"per conto di Bianchi Luigi" in response.data


@freeze_time("2026-05-15 10:00:00+02:00")
def test_pathtracks_new_on_behalf_of_unauthorized_returns_403(
    client, mock_employee_repo_for_resolver, mock_pt_repos_for_pathtracks
):
    _login_admin(client, eh_id=10, sub_cdc_id=42)
    response = client.get("/pathtracks/new?on_behalf_of=999")
    assert response.status_code == 403
