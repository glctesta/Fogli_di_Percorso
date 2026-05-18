"""Test del repository CoordinateRepo (mock cursor SQL Server)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from fdp_app.repos.coordinate_repo import (
    CoordinateRepo,
    ActiveCoordinate,
)


def _make_db(fetchone_row=None):
    db = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone_row
    db.cursor.return_value = cursor
    return db, cursor


def test_find_active_returns_none_when_no_row():
    db, cursor = _make_db(fetchone_row=None)
    repo = CoordinateRepo(db)

    result = repo.find_active(employee_hire_history_id=42)

    assert result is None
    cursor.close.assert_called_once()


def test_find_active_returns_coordinate_when_row_exists():
    row = (
        100,                       # PathTrackCoordinateId
        "Casa Mario",              # PathTrackName
        45.4642,                   # lat (from Coordinates.Lat)
        9.1900,                    # lon (from Coordinates.Long)
        12.345,                    # RoadKmToWorkplace
    )
    db, cursor = _make_db(fetchone_row=row)
    repo = CoordinateRepo(db)

    result = repo.find_active(employee_hire_history_id=42)

    assert isinstance(result, ActiveCoordinate)
    assert result.coordinate_id == 100
    assert result.label == "Casa Mario"
    assert result.lat == 45.4642
    assert result.lon == 9.1900
    assert result.road_km_to_workplace == pytest.approx(12.345)


def test_find_active_query_filters_by_employee_and_dateout_null():
    db, cursor = _make_db(fetchone_row=None)
    repo = CoordinateRepo(db)

    repo.find_active(employee_hire_history_id=42)

    sql_text, *params = cursor.execute.call_args[0]
    assert "EmployeerHireHistoryId = ?" in sql_text
    assert "DateOut IS NULL" in sql_text
    assert params == [42]


def test_insert_creates_geography_point_with_road_km():
    db, cursor = _make_db()
    cursor.fetchone.return_value = (200,)  # new PathTrackCoordinateId via OUTPUT INSERTED
    repo = CoordinateRepo(db)

    new_id = repo.insert(
        employee_hire_history_id=42,
        label="Casa Mario",
        lat=45.4642,
        lon=9.1900,
        road_km_to_workplace=12.345,
    )

    assert new_id == 200
    sql_text, *params = cursor.execute.call_args[0]
    assert "INSERT INTO Employee.fdp.PathTrackCoordinates" in sql_text
    assert "geography::Point(?, ?, 4326)" in sql_text
    # Params: emp_id, label, lat, lon, road_km
    assert params == [42, "Casa Mario", 45.4642, 9.1900, 12.345]
    cursor.close.assert_called_once()


def test_soft_delete_sets_dateout_for_active_record():
    db, cursor = _make_db()
    cursor.rowcount = 1
    repo = CoordinateRepo(db)

    deleted = repo.soft_delete(coordinate_id=100, employee_hire_history_id=42)

    assert deleted is True
    sql_text, *params = cursor.execute.call_args[0]
    assert "UPDATE Employee.fdp.PathTrackCoordinates" in sql_text
    assert "SET DateOut = GETDATE()" in sql_text
    assert "PathTrackCoordinateId = ?" in sql_text
    assert "EmployeerHireHistoryId = ?" in sql_text
    assert "DateOut IS NULL" in sql_text
    assert params == [100, 42]


def test_soft_delete_returns_false_when_nothing_updated():
    db, cursor = _make_db()
    cursor.rowcount = 0
    repo = CoordinateRepo(db)

    deleted = repo.soft_delete(coordinate_id=999, employee_hire_history_id=42)

    assert deleted is False


def test_insert_closes_cursor_on_exception():
    db, cursor = _make_db()
    cursor.execute.side_effect = RuntimeError("DB down")
    repo = CoordinateRepo(db)

    with pytest.raises(RuntimeError):
        repo.insert(
            employee_hire_history_id=42,
            label="x",
            lat=1.0,
            lon=2.0,
            road_km_to_workplace=3.0,
        )
    cursor.close.assert_called_once()
