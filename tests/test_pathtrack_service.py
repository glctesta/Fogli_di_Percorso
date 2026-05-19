"""Test del PathTrackService (workflow DRAFT/SUBMITTED)."""
from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from freezegun import freeze_time

from fdp_app.pathtracks.service import (
    PathTrackService,
    DeadlineClosedError,
    NoActiveCoordinateError,
    NoRateConfiguredError,
    DuplicateDeclarationError,
    InvalidInputError,
    NotADraftError,
)
from fdp_app.repos.coordinate_repo import ActiveCoordinate
from fdp_app.repos.pathtrack_repo import PathTrackRow
from fdp_app.repos.rate_repo import Rate


def _make_service():
    repos = {
        "coordinate": MagicMock(),
        "rate": MagicMock(),
        "registry": MagicMock(),
        "pathtrack": MagicMock(),
        "doc": MagicMock(),
    }
    connection = MagicMock()
    connection.autocommit = True
    svc = PathTrackService(
        coordinate_repo=repos["coordinate"],
        rate_repo=repos["rate"],
        registry_repo=repos["registry"],
        pathtrack_repo=repos["pathtrack"],
        doc_repo=repos["doc"],
        connection_factory=lambda: connection,
    )
    return svc, repos, connection


def _row(status="DRAFT", date_path_track=None):
    return PathTrackRow(
        path_track_id=100,
        registry_id=None if status == "DRAFT" else 500,
        date_path_track=date_path_track or date(2026, 4, 1),
        declarated_path_id=99,
        in_behalf_of_id=None,
        reimbursement_type="CARBURANTE",
        number_of_trips=10,
        road_km=10.0,
        rate_id_used=3,
        taxi_total_eur=None,
        computed_amount_eur=10.0,
        status=status,
        submitted_on=None if status == "DRAFT" else datetime(2026, 5, 3, 10, 0),
    )


# ---- create_draft_fuel --------------------------------------------------

@freeze_time("2026-05-15 10:00:00+02:00")
def test_create_draft_fuel_current_month_happy_path():
    svc, repos, conn = _make_service()
    repos["coordinate"].find_active.return_value = ActiveCoordinate(
        coordinate_id=99, label="Casa", lat=45.0, lon=9.0, road_km_to_workplace=10.0,
    )
    repos["rate"].find_for_date.return_value = Rate(3, 15.0, 1.7)
    repos["pathtrack"].find_active_for_month.return_value = None
    repos["pathtrack"].insert.return_value = 100

    new_id = svc.create_draft_fuel(
        employee_hire_history_id=10,
        date_path_track=date(2026, 5, 1),
        number_of_trips=20,
        sheet_pdf=b"%PDF-1.4 sheet",
        receipt_pdfs=[b"%PDF-1.4 r"],
    )

    assert new_id == 100
    repos["registry"].generate.assert_not_called()  # NO SP call for draft
    insert_kwargs = repos["pathtrack"].insert.call_args.kwargs
    assert insert_kwargs["status"] == "DRAFT"
    assert insert_kwargs["registry_id"] is None
    assert insert_kwargs["submitted_on"] is None
    conn.commit.assert_called_once()


@freeze_time("2026-05-15 10:00:00+02:00")
def test_create_draft_fuel_future_month_rejected():
    svc, repos, _ = _make_service()
    repos["coordinate"].find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 10.0)

    with pytest.raises(DeadlineClosedError):
        svc.create_draft_fuel(
            employee_hire_history_id=10,
            date_path_track=date(2026, 6, 1),  # mese futuro
            number_of_trips=10,
            sheet_pdf=b"%PDF-",
            receipt_pdfs=[b"%PDF-"],
        )


@freeze_time("2026-05-06 10:00:00+02:00")
def test_create_draft_fuel_previous_month_rejected_after_deadline():
    svc, repos, _ = _make_service()
    repos["coordinate"].find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 10.0)

    with pytest.raises(DeadlineClosedError):
        svc.create_draft_fuel(
            employee_hire_history_id=10,
            date_path_track=date(2026, 4, 1),  # aprile, dopo il 5 maggio
            number_of_trips=10,
            sheet_pdf=b"%PDF-",
            receipt_pdfs=[b"%PDF-"],
        )


@freeze_time("2026-05-15 10:00:00+02:00")
def test_create_draft_taxi_current_month_happy_path():
    svc, repos, conn = _make_service()
    repos["coordinate"].find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 10.0)
    repos["pathtrack"].find_active_for_month.return_value = None
    repos["pathtrack"].insert.return_value = 101

    new_id = svc.create_draft_taxi(
        employee_hire_history_id=10,
        date_path_track=date(2026, 5, 1),
        number_of_trips=8,
        receipt_amounts=[12.50, 8.30],
        sheet_pdf=b"%PDF-",
        receipt_pdfs=[b"%PDF-", b"%PDF-"],
    )

    assert new_id == 101
    insert_kwargs = repos["pathtrack"].insert.call_args.kwargs
    assert insert_kwargs["status"] == "DRAFT"
    assert insert_kwargs["taxi_total_eur"] == pytest.approx(20.80)
    repos["registry"].generate.assert_not_called()


# ---- update_draft -------------------------------------------------------

@freeze_time("2026-05-15 10:00:00+02:00")
def test_update_draft_fuel_succeeds_for_current_month_draft():
    svc, repos, conn = _make_service()
    repos["pathtrack"].find_by_id.return_value = _row(status="DRAFT", date_path_track=date(2026, 5, 1))
    repos["coordinate"].find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 12.0)
    repos["rate"].find_for_date.return_value = Rate(3, 15.0, 1.7)

    svc.update_draft_fuel(
        path_track_id=100,
        employee_hire_history_id=10,
        number_of_trips=15,
        sheet_pdf=b"%PDF-",
        receipt_pdfs=[b"%PDF-"],
    )

    repos["pathtrack"].update_draft.assert_called_once()
    repos["doc"].soft_delete_all_for_pathtrack.assert_called_once_with(path_track_id=100)
    conn.commit.assert_called_once()


@freeze_time("2026-05-15 10:00:00+02:00")
def test_update_draft_rejected_when_not_draft():
    svc, repos, _ = _make_service()
    repos["pathtrack"].find_by_id.return_value = _row(status="SUBMITTED", date_path_track=date(2026, 5, 1))

    with pytest.raises(NotADraftError):
        svc.update_draft_fuel(
            path_track_id=100,
            employee_hire_history_id=10,
            number_of_trips=15,
            sheet_pdf=b"%PDF-",
            receipt_pdfs=[b"%PDF-"],
        )


@freeze_time("2026-05-15 10:00:00+02:00")
def test_update_draft_rejected_when_not_found():
    svc, repos, _ = _make_service()
    repos["pathtrack"].find_by_id.return_value = None

    with pytest.raises(NotADraftError):
        svc.update_draft_fuel(
            path_track_id=999,
            employee_hire_history_id=10,
            number_of_trips=15,
            sheet_pdf=b"%PDF-",
            receipt_pdfs=[b"%PDF-"],
        )


# ---- submit -------------------------------------------------------------

@freeze_time("2026-05-03 10:00:00+02:00")
def test_submit_happy_path():
    svc, repos, conn = _make_service()
    repos["pathtrack"].find_by_id.return_value = _row(status="DRAFT", date_path_track=date(2026, 4, 1))
    repos["registry"].generate.return_value = 500
    repos["pathtrack"].mark_as_submitted.return_value = True

    registry_id = svc.submit(
        path_track_id=100,
        employee_hire_history_id=10,
        full_name="Rossi Mario",
    )

    assert registry_id == 500
    repos["registry"].generate.assert_called_once_with(issued_by_full_name="Rossi Mario")
    repos["pathtrack"].mark_as_submitted.assert_called_once_with(
        path_track_id=100, employee_hire_history_id=10, registry_id=500,
    )
    conn.commit.assert_called_once()


@freeze_time("2026-05-15 10:00:00+02:00")
def test_submit_rejected_outside_window():
    svc, repos, _ = _make_service()
    repos["pathtrack"].find_by_id.return_value = _row(status="DRAFT", date_path_track=date(2026, 4, 1))

    with pytest.raises(DeadlineClosedError):
        svc.submit(
            path_track_id=100,
            employee_hire_history_id=10,
            full_name="x",
        )

    repos["registry"].generate.assert_not_called()


@freeze_time("2026-05-03 10:00:00+02:00")
def test_submit_rejected_for_non_draft():
    svc, repos, _ = _make_service()
    repos["pathtrack"].find_by_id.return_value = _row(status="SUBMITTED", date_path_track=date(2026, 4, 1))

    with pytest.raises(NotADraftError):
        svc.submit(
            path_track_id=100,
            employee_hire_history_id=10,
            full_name="x",
        )


@freeze_time("2026-05-03 10:00:00+02:00")
def test_submit_rolls_back_on_sp_failure():
    svc, repos, conn = _make_service()
    repos["pathtrack"].find_by_id.return_value = _row(status="DRAFT", date_path_track=date(2026, 4, 1))
    repos["registry"].generate.side_effect = RuntimeError("SP error")

    with pytest.raises(RuntimeError):
        svc.submit(
            path_track_id=100,
            employee_hire_history_id=10,
            full_name="x",
        )

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
