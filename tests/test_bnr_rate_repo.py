"""Test del repository BnrRateRepo."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from fdp_app.repos.bnr_rate_repo import BnrRate, BnrRateRepo


def _make_db(fetchone=None):
    db = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    db.cursor.return_value = cursor
    return db, cursor


def test_find_standard_for_returns_none_when_no_match():
    db, _ = _make_db(fetchone=None)
    repo = BnrRateRepo(db)
    assert repo.find_standard_for(date(2026, 5, 20)) is None


def test_find_standard_for_returns_rate_when_found():
    db, _ = _make_db(fetchone=(1, 4.9756, "STANDARD", date(2026, 1, 1), None))
    repo = BnrRateRepo(db)
    result = repo.find_standard_for(date(2026, 5, 20))
    assert isinstance(result, BnrRate)
    assert result.rate_id == 1
    assert result.rate_value_ron_per_eur == pytest.approx(4.9756)
    assert result.source == "STANDARD"


def test_find_standard_for_query_filters_by_is_standard_and_date():
    db, cursor = _make_db(fetchone=None)
    repo = BnrRateRepo(db)
    repo.find_standard_for(date(2026, 5, 20))
    sql_text, *params = cursor.execute.call_args[0]
    assert "IsStandard = 1" in sql_text
    assert "ValidFrom <= ?" in sql_text
    assert "ValidTo IS NULL OR ValidTo >= ?" in sql_text
    assert params == [date(2026, 5, 20), date(2026, 5, 20)]


def test_find_latest_cached_for_returns_most_recent():
    db, _ = _make_db(fetchone=(5, 4.97, "BNR", date(2026, 5, 19), None))
    repo = BnrRateRepo(db)
    result = repo.find_latest_cached_for(date(2026, 5, 20))
    assert result is not None
    assert result.rate_value_ron_per_eur == pytest.approx(4.97)
    assert result.source == "BNR"


def test_find_latest_cached_for_returns_none_when_no_history():
    db, _ = _make_db(fetchone=None)
    repo = BnrRateRepo(db)
    assert repo.find_latest_cached_for(date(2026, 5, 20)) is None


def test_insert_returns_new_id():
    db, cursor = _make_db(fetchone=(42,))
    repo = BnrRateRepo(db)
    new_id = repo.insert(
        rate_value_ron_per_eur=4.9756,
        source="BNR",
        valid_from=date(2026, 5, 20),
        valid_to=None,
        is_standard=False,
        user_sys="test",
    )
    assert new_id == 42
    sql_text, *params = cursor.execute.call_args[0]
    assert "INSERT INTO Employee.fdp.BnrRates" in sql_text
    assert 4.9756 in params
    assert "BNR" in params
    assert date(2026, 5, 20) in params
    assert 0 in params  # is_standard=False -> 0
    assert "test" in params


def test_insert_with_is_standard_true_passes_1():
    db, cursor = _make_db(fetchone=(43,))
    repo = BnrRateRepo(db)
    repo.insert(
        rate_value_ron_per_eur=4.97,
        source="STANDARD",
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
        is_standard=True,
        user_sys="admin",
    )
    _sql_text, *params = cursor.execute.call_args[0]
    assert 1 in params  # is_standard=True -> 1


def test_list_standards_returns_admin_rates():
    db = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        (1, 4.9756, "STANDARD", date(2026, 1, 1), None, 1, "admin"),
        (2, 4.97, "STANDARD", date(2025, 1, 1), date(2025, 12, 31), 1, "admin"),
    ]
    db.cursor.return_value = cursor
    repo = BnrRateRepo(db)
    result = repo.list_standards()
    assert len(result) == 2
    assert result[0].rate_id == 1
    assert result[1].valid_to == date(2025, 12, 31)


def test_list_recent_returns_recent_history():
    db = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        (10, 4.97, "BNR", date(2026, 5, 19), None, 0, "system"),
    ]
    db.cursor.return_value = cursor
    repo = BnrRateRepo(db)
    result = repo.list_recent(limit=10)
    assert len(result) == 1
    assert result[0].source == "BNR"
