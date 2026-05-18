"""Test del repository PathTrackRepo."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from fdp_app.repos.pathtrack_repo import (
    PathTrackRepo,
    PathTrackRow,
)


def _make_db(fetchone=None, fetchall=None):
    db = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    cursor.fetchall.return_value = fetchall or []
    db.cursor.return_value = cursor
    return db, cursor


def test_find_active_for_month_returns_none_when_no_row():
    db, _ = _make_db(fetchone=None)
    repo = PathTrackRepo(db)

    result = repo.find_active_for_month(
        employee_hire_history_id=10, date_path_track=date(2026, 4, 1)
    )
    assert result is None


def test_find_active_for_month_returns_row():
    db, cursor = _make_db(fetchone=(
        100, 500, date(2026, 4, 1), 99, None,
        "CARBURANTE", 15, 10.5, 3, None, 53.55,
    ))
    repo = PathTrackRepo(db)

    result = repo.find_active_for_month(
        employee_hire_history_id=10, date_path_track=date(2026, 4, 1)
    )

    assert isinstance(result, PathTrackRow)
    assert result.path_track_id == 100
    assert result.registry_id == 500
    assert result.reimbursement_type == "CARBURANTE"
    assert result.computed_amount_eur == pytest.approx(53.55)


def test_insert_returns_new_id():
    db, cursor = _make_db(fetchone=(200,))
    repo = PathTrackRepo(db)

    new_id = repo.insert(
        employee_hire_history_id=10,
        registry_id=500,
        date_path_track=date(2026, 4, 1),
        declarated_path_id=99,
        in_behalf_of_id=None,
        reimbursement_type="CARBURANTE",
        number_of_trips=15,
        road_km=10.5,
        rate_id_used=3,
        taxi_total_eur=None,
        computed_amount_eur=53.55,
    )

    assert new_id == 200
    sql_text, *params = cursor.execute.call_args[0]
    assert "INSERT INTO Employee.fdp.PathTracks" in sql_text
    assert 10 in params
    assert 500 in params
    assert "CARBURANTE" in params


def test_soft_delete_returns_true_when_row_deleted():
    db, cursor = _make_db()
    cursor.rowcount = 1
    repo = PathTrackRepo(db)

    deleted = repo.soft_delete(path_track_id=100, employee_hire_history_id=10)

    assert deleted is True
    sql_text, *params = cursor.execute.call_args[0]
    assert "SET DateOut = GETDATE()" in sql_text
    assert "EmployeeHireHistoryId = ?" in sql_text
    assert params == [100, 10]


def test_soft_delete_returns_false_when_no_rows_affected():
    db, cursor = _make_db()
    cursor.rowcount = 0
    repo = PathTrackRepo(db)
    assert repo.soft_delete(path_track_id=999, employee_hire_history_id=10) is False


def test_list_for_employee_returns_rows():
    db, cursor = _make_db(fetchall=[
        (1, 100, date(2026, 4, 1), 99, None, "CARBURANTE", 15, 10.5, 3, None, 53.55),
        (2, 101, date(2026, 3, 1), 99, None, "TAXI", 10, 8.0, None, 45.0, 45.0),
    ])
    repo = PathTrackRepo(db)

    rows = repo.list_for_employee(employee_hire_history_id=10)

    assert len(rows) == 2
    assert rows[0].path_track_id == 1
    assert rows[1].reimbursement_type == "TAXI"
