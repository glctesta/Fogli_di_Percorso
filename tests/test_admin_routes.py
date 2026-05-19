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
