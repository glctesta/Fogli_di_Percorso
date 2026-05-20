"""Test del /admin/bnr-rates CRUD."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_bnr_repo():
    with patch("fdp_app.admin.routes.BnrRateRepo") as cls:
        instance = MagicMock()
        instance.list_standards.return_value = []
        instance.list_recent.return_value = []
        cls.return_value = instance
        yield instance


def _login_admin(client, eh_id=10, sub_cdc_id=42, fc=70):
    with client.session_transaction() as sess:
        sess["user_id"] = eh_id
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = sub_cdc_id
        sess["function_code"] = fc


def test_bnr_rates_requires_admin(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["function_code"] = 50
    response = client.get("/admin/bnr-rates")
    assert response.status_code == 403


def test_bnr_rates_empty_state(client, mock_bnr_repo):
    _login_admin(client)
    response = client.get("/admin/bnr-rates")
    assert response.status_code == 200
    assert b"Nessun tasso STANDARD configurato" in response.data or b"Nessun tasso ancora acquisito" in response.data


def test_bnr_rates_lists_standards(client, mock_bnr_repo):
    from fdp_app.repos.bnr_rate_repo import BnrRate
    _login_admin(client)
    mock_bnr_repo.list_standards.return_value = [
        BnrRate(rate_id=1, rate_value_ron_per_eur=4.9756, source="STANDARD",
                valid_from=date(2026, 1, 1), valid_to=None,
                is_standard=True, user_sys="admin"),
    ]
    response = client.get("/admin/bnr-rates")
    assert response.status_code == 200
    assert b"4.9756" in response.data
    assert b"2026-01-01" in response.data


def test_bnr_rates_create_standard(client, mock_bnr_repo):
    _login_admin(client)
    mock_bnr_repo.insert.return_value = 99
    response = client.post(
        "/admin/bnr-rates",
        data={
            "rate_value": "4.9876",
            "valid_from": "2026-06-01",
            "valid_to": "2026-12-31",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    mock_bnr_repo.insert.assert_called_once()
    kwargs = mock_bnr_repo.insert.call_args.kwargs
    assert kwargs["rate_value_ron_per_eur"] == pytest.approx(4.9876)
    assert kwargs["source"] == "STANDARD"
    assert kwargs["valid_from"] == date(2026, 6, 1)
    assert kwargs["valid_to"] == date(2026, 12, 31)
    assert kwargs["is_standard"] is True


def test_bnr_rates_create_without_valid_to(client, mock_bnr_repo):
    _login_admin(client)
    mock_bnr_repo.insert.return_value = 100
    response = client.post(
        "/admin/bnr-rates",
        data={
            "rate_value": "4.97",
            "valid_from": "2026-06-01",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    kwargs = mock_bnr_repo.insert.call_args.kwargs
    assert kwargs["valid_to"] is None


def test_bnr_rates_create_rejects_invalid_rate(client, mock_bnr_repo):
    _login_admin(client)
    response = client.post(
        "/admin/bnr-rates",
        data={"rate_value": "not-a-number", "valid_from": "2026-06-01"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    mock_bnr_repo.insert.assert_not_called()


def test_bnr_rates_create_rejects_negative_rate(client, mock_bnr_repo):
    _login_admin(client)
    response = client.post(
        "/admin/bnr-rates",
        data={"rate_value": "-1", "valid_from": "2026-06-01"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    mock_bnr_repo.insert.assert_not_called()


def test_bnr_rates_create_rejects_invalid_date(client, mock_bnr_repo):
    _login_admin(client)
    response = client.post(
        "/admin/bnr-rates",
        data={"rate_value": "4.97", "valid_from": "not-a-date"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    mock_bnr_repo.insert.assert_not_called()
