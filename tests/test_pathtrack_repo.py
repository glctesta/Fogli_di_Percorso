"""Test del repository PathTrackRepo (con stato DRAFT/SUBMITTED)."""
from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from fdp_app.repos.pathtrack_repo import (
    PathTrackRepo,
    PathTrackRow,
    PathTrackWithEmployee,
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
    assert repo.find_active_for_month(
        employee_hire_history_id=10, date_path_track=date(2026, 4, 1)
    ) is None


def test_find_active_for_month_returns_row_with_status():
    db, _ = _make_db(fetchone=(
        100, None, date(2026, 4, 1), 99, None,
        "CARBURANTE", 15, 10.5, 3, None, 53.55,
        "DRAFT", None, None,
    ))
    repo = PathTrackRepo(db)

    result = repo.find_active_for_month(
        employee_hire_history_id=10, date_path_track=date(2026, 4, 1)
    )

    assert isinstance(result, PathTrackRow)
    assert result.path_track_id == 100
    assert result.registry_id is None  # DRAFT has no registry_id
    assert result.status == "DRAFT"
    assert result.submitted_on is None
    assert result.computed_amount_eur == pytest.approx(53.55)


def test_find_active_for_month_returns_submitted_row():
    submitted_dt = datetime(2026, 5, 3, 10, 0, 0)
    db, _ = _make_db(fetchone=(
        100, 500, date(2026, 4, 1), 99, None,
        "CARBURANTE", 15, 10.5, 3, None, 53.55,
        "SUBMITTED", submitted_dt, None,
    ))
    repo = PathTrackRepo(db)

    result = repo.find_active_for_month(
        employee_hire_history_id=10, date_path_track=date(2026, 4, 1)
    )

    assert result.registry_id == 500
    assert result.status == "SUBMITTED"
    assert result.submitted_on == submitted_dt


def test_insert_default_status_is_draft_with_no_registry():
    db, cursor = _make_db(fetchone=(200,))
    repo = PathTrackRepo(db)

    new_id = repo.insert(
        employee_hire_history_id=10,
        registry_id=None,  # draft has no registry
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
    assert "Status" in sql_text
    assert "DRAFT" in params  # default status DRAFT
    assert None in params  # registry_id NULL


def test_insert_can_create_submitted_directly():
    """Caller may pass status='SUBMITTED' and a registry_id for retro-compat."""
    db, cursor = _make_db(fetchone=(201,))
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
        status="SUBMITTED",
        submitted_on=datetime(2026, 5, 3, 10, 0, 0),
    )

    assert new_id == 201
    sql_text, *params = cursor.execute.call_args[0]
    assert "SUBMITTED" in params
    assert 500 in params


def test_update_draft_succeeds_when_row_is_draft():
    db, cursor = _make_db()
    cursor.rowcount = 1
    repo = PathTrackRepo(db)

    ok = repo.update_draft(
        path_track_id=100,
        employee_hire_history_id=10,
        reimbursement_type="TAXI",
        number_of_trips=20,
        road_km=10.0,
        rate_id_used=None,
        taxi_total_eur=42.50,
        computed_amount_eur=42.50,
    )

    assert ok is True
    sql_text, *params = cursor.execute.call_args[0]
    assert "UPDATE Employee.fdp.PathTracks" in sql_text
    assert "Status = 'DRAFT'" in sql_text
    # Params order: 6 update fields, then path_track_id, employee_hire_history_id
    assert params[0] == "TAXI"
    assert params[6] == 100
    assert params[7] == 10


def test_update_draft_returns_false_when_not_draft():
    db, cursor = _make_db()
    cursor.rowcount = 0
    repo = PathTrackRepo(db)

    ok = repo.update_draft(
        path_track_id=999,
        employee_hire_history_id=10,
        reimbursement_type="CARBURANTE",
        number_of_trips=1,
        road_km=1.0,
        rate_id_used=3,
        taxi_total_eur=None,
        computed_amount_eur=1.0,
    )
    assert ok is False


def test_mark_as_submitted_sets_status_and_registry():
    db, cursor = _make_db()
    cursor.rowcount = 1
    repo = PathTrackRepo(db)

    ok = repo.mark_as_submitted(
        path_track_id=100, employee_hire_history_id=10, registry_id=500,
    )

    assert ok is True
    sql_text, *params = cursor.execute.call_args[0]
    assert "Status" in sql_text and "'SUBMITTED'" in sql_text
    assert "GETDATE()" in sql_text
    assert "Status = 'DRAFT'" in sql_text  # the WHERE clause guards against double-submit
    assert "BnrRateRonPerEur" in sql_text
    # Params: registry_id, bnr_rate, path_track_id, employee_hire_history_id
    assert params == [500, None, 100, 10]


def test_mark_as_submitted_returns_false_when_not_draft():
    db, cursor = _make_db()
    cursor.rowcount = 0
    repo = PathTrackRepo(db)

    ok = repo.mark_as_submitted(
        path_track_id=999, employee_hire_history_id=10, registry_id=500,
    )
    assert ok is False


def test_soft_delete_only_deletes_drafts():
    db, cursor = _make_db()
    cursor.rowcount = 1
    repo = PathTrackRepo(db)

    deleted = repo.soft_delete(path_track_id=100, employee_hire_history_id=10)

    assert deleted is True
    sql_text, _ = cursor.execute.call_args[0][0], cursor.execute.call_args[0][1:]
    assert "Status = 'DRAFT'" in sql_text


def test_soft_delete_returns_false_when_no_draft_match():
    db, cursor = _make_db()
    cursor.rowcount = 0
    repo = PathTrackRepo(db)
    assert repo.soft_delete(path_track_id=999, employee_hire_history_id=10) is False


def test_list_for_employee_returns_rows_with_status():
    db, cursor = _make_db(fetchall=[
        (1, None, date(2026, 4, 1), 99, None, "CARBURANTE", 15, 10.5, 3, None, 53.55, "DRAFT", None, None),
        (2, 600, date(2026, 3, 1), 99, None, "TAXI", 10, 8.0, None, 45.0, 45.0, "SUBMITTED", datetime(2026, 4, 5, 12, 0), None),
    ])
    repo = PathTrackRepo(db)

    rows = repo.list_for_employee(employee_hire_history_id=10)

    assert len(rows) == 2
    assert rows[0].status == "DRAFT"
    assert rows[0].registry_id is None
    assert rows[1].status == "SUBMITTED"
    assert rows[1].registry_id == 600


def test_list_for_sub_cdc_no_filters():
    db, cursor = _make_db(fetchall=[
        (1, None, date(2026, 5, 1), 99, None, "CARBURANTE", 15, 10.5, 3, None, 53.55, "DRAFT", None, None, "Bianchi", "Luigi"),
        (2, 600, date(2026, 4, 1), 99, None, "TAXI", 10, 8.0, None, 45.0, 45.0, "SUBMITTED", datetime(2026, 5, 5), None, "Verdi", "Maria"),
    ])
    repo = PathTrackRepo(db)
    result = repo.list_for_sub_cdc(sub_cdc_id=42)

    assert len(result) == 2
    assert isinstance(result[0], PathTrackWithEmployee)
    assert result[0].employee_full_name == "Bianchi Luigi"
    assert result[0].row.status == "DRAFT"
    assert result[1].employee_full_name == "Verdi Maria"
    assert result[1].row.computed_amount_eur == pytest.approx(45.0)


def test_list_for_sub_cdc_with_year_month_filter():
    db, cursor = _make_db(fetchall=[])
    repo = PathTrackRepo(db)
    repo.list_for_sub_cdc(sub_cdc_id=42, year=2026, month=4)

    sql_text, *params = cursor.execute.call_args[0]
    assert "YEAR(pt.DatePathTrack) = ?" in sql_text
    assert "MONTH(pt.DatePathTrack) = ?" in sql_text
    assert params == [42, 2026, 4]


def test_list_for_sub_cdc_with_type_filter():
    db, cursor = _make_db(fetchall=[])
    repo = PathTrackRepo(db)
    repo.list_for_sub_cdc(sub_cdc_id=42, reimbursement_type="TAXI")

    sql_text, *params = cursor.execute.call_args[0]
    assert "pt.ReimbursementType = ?" in sql_text
    assert "TAXI" in params


def test_list_for_sub_cdc_uses_coalesce_for_in_behalf_of():
    db, cursor = _make_db(fetchall=[])
    repo = PathTrackRepo(db)
    repo.list_for_sub_cdc(sub_cdc_id=42)
    sql_text, *_ = cursor.execute.call_args[0]
    assert "COALESCE(pt.InBehalfOfId, pt.EmployeeHireHistoryId)" in sql_text


def test_insert_passes_thirteen_positional_params_to_match_sql_placeholders():
    """Regression test for CRITICAL bug: SQL has 13 ? placeholders, insert()
    must pass exactly 13 positional parameters to cursor.execute()."""
    db, cursor = _make_db(fetchone=(42,))
    repo = PathTrackRepo(db)
    repo.insert(
        employee_hire_history_id=10,
        registry_id=None,
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
    # cursor.execute(sql, *params); call_args has (sql, *params) in args
    args = cursor.execute.call_args[0]
    sql_text = args[0]
    params = args[1:]
    placeholder_count = sql_text.count("?")
    assert placeholder_count == len(params), (
        f"Mismatch: SQL has {placeholder_count} placeholders, "
        f"but {len(params)} parameters were passed"
    )
