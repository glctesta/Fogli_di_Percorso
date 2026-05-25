"""Test del repository RateRepo."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from fdp_app.repos.rate_repo import RateRepo, Rate


def _make_db(fetchone=None):
    db = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    db.cursor.return_value = cursor
    return db, cursor


def test_find_for_date_returns_none_when_no_match():
    db, cursor = _make_db(fetchone=None)
    repo = RateRepo(db)

    result = repo.find_for_date(date(2026, 4, 1))

    assert result is None
    cursor.close.assert_called_once()


def test_find_for_date_returns_rate_when_found():
    db, cursor = _make_db(fetchone=(7, 15.00, 1.700))
    repo = RateRepo(db)

    result = repo.find_for_date(date(2026, 4, 1))

    assert isinstance(result, Rate)
    assert result.rate_id == 7
    assert result.avg_consumption_km_l == pytest.approx(15.00)
    assert result.avg_fuel_price_eur_l == pytest.approx(1.700)


def test_find_for_date_query_uses_validity_window():
    db, cursor = _make_db(fetchone=None)
    repo = RateRepo(db)

    repo.find_for_date(date(2026, 4, 1))

    sql_text, *params = cursor.execute.call_args[0]
    assert "ValidFrom <= ?" in sql_text
    assert "ValidTo IS NULL OR ValidTo >= ?" in sql_text
    assert params == [date(2026, 4, 1), date(2026, 4, 1)]


def test_rate_dataclass_audit_fields_default_to_none_or_empty():
    r = Rate(rate_id=1, avg_consumption_km_l=15.0, avg_fuel_price_eur_l=1.7)
    assert r.valid_from is None
    assert r.valid_to is None
    assert r.user_sys == ""


def test_rate_dataclass_accepts_audit_fields():
    r = Rate(
        rate_id=1, avg_consumption_km_l=15.0, avg_fuel_price_eur_l=1.7,
        valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31),
        user_sys="admin",
    )
    assert r.valid_from == date(2026, 1, 1)
    assert r.valid_to == date(2026, 12, 31)
    assert r.user_sys == "admin"
