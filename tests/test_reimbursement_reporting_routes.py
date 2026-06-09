"""Test route sezione report rimborsi."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fdp_app.repos.reimbursement_reporting_repo import ReimbursementReportRow


class _SettingsWithPermission:
    REIMBURSEMENT_REPORT_ALLOWED_USER_IDS = (10,)
    REIMBURSEMENT_REPORT_ALLOWED_FUNCTION_CODES = ()


class _SettingsWithoutPermission:
    REIMBURSEMENT_REPORT_ALLOWED_USER_IDS = ()
    REIMBURSEMENT_REPORT_ALLOWED_FUNCTION_CODES = ()


def _login(client, *, user_id=10, fc=65, sub_cdc_id=42):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = sub_cdc_id
        sess["function_code"] = fc


def _row(employee_id=101, surname="Rossi", name="Mario", **overrides):
    defaults = dict(
        employee_hire_history_id=employee_id,
        employee_surname=surname,
        employee_name=name,
        declared_amount_eur=100.0,
        additional_amount_eur=20.0,
        deduction_amount_eur=10.0,
        notes="ok",
        last_updated_on=None,
    )
    defaults.update(overrides)
    return ReimbursementReportRow(**defaults)


@pytest.fixture
def mock_repo():
    with patch("fdp_app.reimbursement_reporting.routes.ReimbursementReportingRepo") as cls:
        instance = MagicMock()
        instance.list_month_summary.return_value = [_row()]
        cls.return_value = instance
        yield instance


def test_index_requires_permission(client, app):
    app.config["_settings_cls"] = _SettingsWithoutPermission
    _login(client)

    with patch("fdp_app.auth.decorators.can_access_reimbursement_reporting", return_value=False):
        response = client.get("/reimbursement-reporting")
    assert response.status_code == 403


def test_index_renders_for_allowed_user(client, app, mock_repo):
    app.config["_settings_cls"] = _SettingsWithPermission
    _login(client)

    response = client.get("/reimbursement-reporting?year=2026&month=5")
    assert response.status_code == 200
    assert b"Rossi Mario" in response.data
    kwargs = mock_repo.list_month_summary.call_args.kwargs
    assert kwargs["sub_cdc_id"] == 42
    assert kwargs["year"] == 2026
    assert kwargs["month"] == 5


def test_save_adjustment_calls_upsert(client, app, mock_repo):
    app.config["_settings_cls"] = _SettingsWithPermission
    _login(client)

    response = client.post(
        "/reimbursement-reporting/adjustments",
        data={
            "year": "2026",
            "month": "5",
            "employee_id": "101",
            "additional_amount_eur": "12.50",
            "deduction_amount_eur": "2.50",
            "notes": "Test",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    kwargs = mock_repo.upsert_adjustment.call_args.kwargs
    assert kwargs["employee_hire_history_id"] == 101
    assert kwargs["additional_amount_eur"] == 12.5
    assert kwargs["deduction_amount_eur"] == 2.5


def test_export_all_returns_xlsx(client, app, mock_repo):
    app.config["_settings_cls"] = _SettingsWithPermission
    _login(client)

    response = client.get("/reimbursement-reporting/export?year=2026&month=5")
    assert response.status_code == 200
    assert response.mimetype.startswith("application/vnd.openxmlformats")
    assert "rimborso-effettivo-2026-05.xlsx" in response.headers.get("Content-Disposition", "")


def test_export_all_non_zero_filter_changes_filename_and_rows(client, app, mock_repo):
    app.config["_settings_cls"] = _SettingsWithPermission
    _login(client)
    mock_repo.list_month_summary.return_value = [
        _row(employee_id=101),
        _row(employee_id=102, declared_amount_eur=0.0, additional_amount_eur=0.0, deduction_amount_eur=0.0),
    ]

    response = client.get("/reimbursement-reporting/export?year=2026&month=5&non_zero_only=1")
    assert response.status_code == 200
    assert "rimborso-effettivo-2026-05-nonzero.xlsx" in response.headers.get("Content-Disposition", "")


def test_export_employee_404_when_missing(client, app, mock_repo):
    app.config["_settings_cls"] = _SettingsWithPermission
    _login(client)
    mock_repo.list_month_summary.return_value = []

    response = client.get("/reimbursement-reporting/export/999?year=2026&month=5")
    assert response.status_code == 404


def test_index_keeps_selected_employee_visible_with_non_zero_filter(client, app, mock_repo):
    app.config["_settings_cls"] = _SettingsWithPermission
    _login(client)
    mock_repo.list_month_summary.return_value = [
        _row(employee_id=101, declared_amount_eur=0.0, additional_amount_eur=0.0, deduction_amount_eur=0.0),
    ]

    response = client.get(
        "/reimbursement-reporting?year=2026&month=5&employee_id=101&non_zero_only=1"
    )
    assert response.status_code == 200
    assert b"Dati aggiuntivi per" in response.data


def test_export_employee_non_zero_filter_returns_404_for_zero_effective(client, app, mock_repo):
    app.config["_settings_cls"] = _SettingsWithPermission
    _login(client)
    mock_repo.list_month_summary.return_value = [
        _row(employee_id=101, declared_amount_eur=0.0, additional_amount_eur=0.0, deduction_amount_eur=0.0),
    ]

    response = client.get(
        "/reimbursement-reporting/export/101?year=2026&month=5&non_zero_only=1"
    )
    assert response.status_code == 404


def test_export_employee_non_zero_filter_adds_filename_suffix(client, app, mock_repo):
    app.config["_settings_cls"] = _SettingsWithPermission
    _login(client)

    response = client.get(
        "/reimbursement-reporting/export/101?year=2026&month=5&non_zero_only=1"
    )
    assert response.status_code == 200
    assert "rimborso-utente-101-2026-05-nonzero.xlsx" in response.headers.get(
        "Content-Disposition", ""
    )
