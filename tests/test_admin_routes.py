"""Test E2E delle route /admin/*."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fdp_app.repos.employee_repo import RepresentableEmployee


@pytest.fixture
def mock_employee_repo():
    with patch("fdp_app.admin.routes.EmployeeRepo") as cls:
        instance = MagicMock()
        instance.find_representable_for.return_value = []
        cls.return_value = instance
        yield instance


def _login_admin(client, eh_id=10, sub_cdc_id=42, fc=70):
    with client.session_transaction() as sess:
        sess["user_id"] = eh_id
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = sub_cdc_id
        sess["function_code"] = fc


def _login_non_admin(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["function_code"] = 50  # not admin


def test_representable_requires_login(client):
    response = client.get("/admin/representable", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_representable_forbidden_when_not_admin(client):
    _login_non_admin(client)
    response = client.get("/admin/representable")
    assert response.status_code == 403


def test_representable_lists_employees(client, mock_employee_repo):
    _login_admin(client, sub_cdc_id=42, fc=70)
    mock_employee_repo.find_representable_for.return_value = [
        RepresentableEmployee(101, "Bianchi", "Luigi", 42, 50),
        RepresentableEmployee(102, "Verdi", "Maria", 42, 30),
    ]
    response = client.get("/admin/representable")
    assert response.status_code == 200
    assert b"Bianchi Luigi" in response.data
    assert b"Verdi Maria" in response.data
    # Verify query parameters
    mock_employee_repo.find_representable_for.assert_called_once()
    kwargs = mock_employee_repo.find_representable_for.call_args.kwargs
    assert kwargs["sub_cdc_id"] == 42
    assert kwargs["min_function_code"] == 60


def test_representable_empty_state(client, mock_employee_repo):
    _login_admin(client)
    mock_employee_repo.find_representable_for.return_value = []
    response = client.get("/admin/representable")
    assert response.status_code == 200
    assert b"Nessun collega rappresentabile" in response.data


@pytest.fixture
def mock_pathtrack_repo_admin():
    with patch("fdp_app.admin.routes.PathTrackRepo") as cls:
        instance = MagicMock()
        instance.list_for_sub_cdc.return_value = []
        cls.return_value = instance
        yield instance


def test_history_requires_login(client):
    response = client.get("/admin/history", follow_redirects=False)
    assert response.status_code == 302


def test_history_forbidden_when_not_admin(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["function_code"] = 50
    response = client.get("/admin/history")
    assert response.status_code == 403


def test_history_lists_rows(client, mock_pathtrack_repo_admin):
    from fdp_app.repos.pathtrack_repo import PathTrackRow, PathTrackWithEmployee
    from datetime import date as Date
    _login_admin(client, sub_cdc_id=42)
    mock_pathtrack_repo_admin.list_for_sub_cdc.return_value = [
        PathTrackWithEmployee(
            row=PathTrackRow(
                path_track_id=1, registry_id=None, date_path_track=Date(2026, 5, 1),
                declarated_path_id=99, in_behalf_of_id=None,
                reimbursement_type="CARBURANTE", number_of_trips=15, road_km=10.0,
                rate_id_used=3, taxi_total_eur=None, computed_amount_eur=53.55,
                status="DRAFT", submitted_on=None,
            ),
            employee_surname="Bianchi", employee_name="Luigi",
        ),
    ]
    response = client.get("/admin/history?year=2026&month=5")
    assert response.status_code == 200
    assert b"Bianchi Luigi" in response.data
    assert b"BOZZA" in response.data
    # Filters passed correctly
    kwargs = mock_pathtrack_repo_admin.list_for_sub_cdc.call_args.kwargs
    assert kwargs["sub_cdc_id"] == 42
    assert kwargs["year"] == 2026
    assert kwargs["month"] == 5


def test_history_filters_by_type(client, mock_pathtrack_repo_admin):
    _login_admin(client)
    response = client.get("/admin/history?type=taxi")
    assert response.status_code == 200
    kwargs = mock_pathtrack_repo_admin.list_for_sub_cdc.call_args.kwargs
    assert kwargs["reimbursement_type"] == "TAXI"  # uppercased


def test_view_pathtrack_requires_admin(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["function_code"] = 50
    response = client.get("/admin/pathtracks/100")
    assert response.status_code == 403


def test_view_pathtrack_admin_shows_subordinate_detail(client, mock_pathtrack_repo_admin):
    from fdp_app.repos.pathtrack_repo import PathTrackRow
    from datetime import date as Date
    _login_admin(client, sub_cdc_id=42)
    with patch("fdp_app.admin.routes.PathTrackDocRepo") as doc_cls:
        doc = MagicMock()
        doc.list_for_pathtrack.return_value = []
        doc_cls.return_value = doc
        mock_pathtrack_repo_admin.find_by_id_in_sub_cdc.return_value = PathTrackRow(
            path_track_id=100, registry_id=500, date_path_track=Date(2026, 4, 1),
            declarated_path_id=99, in_behalf_of_id=None,
            reimbursement_type="CARBURANTE", number_of_trips=20, road_km=10.0,
            rate_id_used=3, taxi_total_eur=None, computed_amount_eur=53.55,
            status="SUBMITTED", submitted_on=None,
        )
        response = client.get("/admin/pathtracks/100")
        assert response.status_code == 200
        assert b"INVIATA" in response.data
        assert b"sola consultazione" in response.data.lower()


def test_view_pathtrack_admin_404_when_other_sub_cdc(client, mock_pathtrack_repo_admin):
    _login_admin(client, sub_cdc_id=42)
    mock_pathtrack_repo_admin.find_by_id_in_sub_cdc.return_value = None
    response = client.get("/admin/pathtracks/999")
    assert response.status_code == 404
