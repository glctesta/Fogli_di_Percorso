"""Test del /admin/fuel-rates CRUD."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_rate_repo():
    with patch("fdp_app.admin.routes.RateRepo") as cls:
        instance = MagicMock()
        instance.list_recent.return_value = []
        cls.return_value = instance
        yield instance


def _login_admin(client, eh_id=10, sub_cdc_id=42, fc=70):
    with client.session_transaction() as sess:
        sess["user_id"] = eh_id
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = sub_cdc_id
        sess["function_code"] = fc


def test_fuel_rates_requires_admin(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["function_code"] = 50
    response = client.get("/admin/fuel-rates")
    assert response.status_code == 403


def test_fuel_rates_empty_state(client, mock_rate_repo):
    _login_admin(client)
    response = client.get("/admin/fuel-rates")
    assert response.status_code == 200
    assert b"Nessuna tariffa" in response.data


def test_fuel_rates_lists_rates(client, mock_rate_repo):
    from fdp_app.repos.rate_repo import Rate
    _login_admin(client)
    mock_rate_repo.list_recent.return_value = [
        Rate(
            rate_id=7, avg_consumption_km_l=15.0, avg_fuel_price_eur_l=1.700,
            valid_from=date(2026, 6, 1), valid_to=None, user_sys="Rossi Mario",
        ),
    ]
    response = client.get("/admin/fuel-rates")
    assert response.status_code == 200
    assert b"15.00" in response.data
    assert b"1.700" in response.data
    assert b"2026-06-01" in response.data
    assert b"Rossi Mario" in response.data


def test_fuel_rates_create(client, mock_rate_repo):
    _login_admin(client)
    mock_rate_repo.insert.return_value = 77
    response = client.post(
        "/admin/fuel-rates",
        data={
            "avg_consumption_km_l": "15.00",
            "avg_fuel_price_eur_l": "1.700",
            "valid_from": "2026-06-01",
            "valid_to": "2026-12-31",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    mock_rate_repo.insert.assert_called_once()
    kwargs = mock_rate_repo.insert.call_args.kwargs
    assert kwargs["avg_consumption_km_l"] == pytest.approx(15.0)
    assert kwargs["avg_fuel_price_eur_l"] == pytest.approx(1.700)
    assert kwargs["valid_from"] == date(2026, 6, 1)
    assert kwargs["valid_to"] == date(2026, 12, 31)
    assert kwargs["user_sys"] == "Rossi Mario"


def test_fuel_rates_create_without_valid_to(client, mock_rate_repo):
    _login_admin(client)
    mock_rate_repo.insert.return_value = 78
    response = client.post(
        "/admin/fuel-rates",
        data={
            "avg_consumption_km_l": "15.00",
            "avg_fuel_price_eur_l": "1.700",
            "valid_from": "2026-06-01",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert mock_rate_repo.insert.call_args.kwargs["valid_to"] is None


def test_fuel_rates_create_rejects_invalid_consumption(client, mock_rate_repo):
    _login_admin(client)
    response = client.post(
        "/admin/fuel-rates",
        data={
            "avg_consumption_km_l": "not-a-number",
            "avg_fuel_price_eur_l": "1.7",
            "valid_from": "2026-06-01",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    mock_rate_repo.insert.assert_not_called()


def test_fuel_rates_create_rejects_non_positive_consumption(client, mock_rate_repo):
    _login_admin(client)
    response = client.post(
        "/admin/fuel-rates",
        data={
            "avg_consumption_km_l": "0",
            "avg_fuel_price_eur_l": "1.7",
            "valid_from": "2026-06-01",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    mock_rate_repo.insert.assert_not_called()


def test_fuel_rates_create_rejects_non_positive_price(client, mock_rate_repo):
    _login_admin(client)
    response = client.post(
        "/admin/fuel-rates",
        data={
            "avg_consumption_km_l": "15",
            "avg_fuel_price_eur_l": "-0.5",
            "valid_from": "2026-06-01",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    mock_rate_repo.insert.assert_not_called()


def test_fuel_rates_create_rejects_invalid_valid_from(client, mock_rate_repo):
    _login_admin(client)
    response = client.post(
        "/admin/fuel-rates",
        data={
            "avg_consumption_km_l": "15",
            "avg_fuel_price_eur_l": "1.7",
            "valid_from": "not-a-date",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    mock_rate_repo.insert.assert_not_called()


def test_fuel_rates_create_rejects_valid_to_before_valid_from(client, mock_rate_repo):
    _login_admin(client)
    response = client.post(
        "/admin/fuel-rates",
        data={
            "avg_consumption_km_l": "15",
            "avg_fuel_price_eur_l": "1.7",
            "valid_from": "2026-06-01",
            "valid_to": "2026-05-15",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    mock_rate_repo.insert.assert_not_called()


def test_fuel_rates_create_rejects_invalid_valid_to(client, mock_rate_repo):
    _login_admin(client)
    response = client.post(
        "/admin/fuel-rates",
        data={
            "avg_consumption_km_l": "15",
            "avg_fuel_price_eur_l": "1.7",
            "valid_from": "2026-06-01",
            "valid_to": "not-a-date",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    mock_rate_repo.insert.assert_not_called()


def test_fuel_rates_create_handles_duplicate_valid_from(client, mock_rate_repo):
    _login_admin(client)
    mock_rate_repo.insert.side_effect = Exception(
        "Violation of UNIQUE KEY constraint 'UX_Rates_ValidFrom'."
    )
    response = client.post(
        "/admin/fuel-rates",
        data={
            "avg_consumption_km_l": "15",
            "avg_fuel_price_eur_l": "1.7",
            "valid_from": "2026-06-01",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    mock_rate_repo.insert.assert_called_once()
    # the page renders and does not 500
    assert b"Tariffe rimborso km" in response.data
    # the admin sees a danger flash; silent swallow would defeat Task 7
    assert b"Esiste gia" in response.data


def test_fuel_rates_create_propagates_unrelated_db_errors(client, mock_rate_repo):
    _login_admin(client)
    mock_rate_repo.insert.side_effect = Exception("network timeout")
    # With TESTING=True Flask re-raises unhandled exceptions from the test
    # client instead of returning a 500 — we assert that propagation.
    with pytest.raises(Exception, match="network timeout"):
        client.post(
            "/admin/fuel-rates",
            data={
                "avg_consumption_km_l": "15",
                "avg_fuel_price_eur_l": "1.7",
                "valid_from": "2026-06-01",
            },
        )
