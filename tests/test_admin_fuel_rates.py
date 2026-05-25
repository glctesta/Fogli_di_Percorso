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
