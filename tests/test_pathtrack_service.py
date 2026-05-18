"""Test del PathTrackService (orchestrazione transazionale)."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from fdp_app.pathtracks.service import (
    PathTrackService,
    DeadlineClosedError,
    NoActiveCoordinateError,
    NoRateConfiguredError,
    DuplicateDeclarationError,
    InvalidInputError,
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


def test_create_fuel_happy_path():
    svc, repos, conn = _make_service()
    repos["coordinate"].find_active.return_value = ActiveCoordinate(
        coordinate_id=99, label="Casa", lat=45.0, lon=9.0, road_km_to_workplace=10.0,
    )
    repos["rate"].find_for_date.return_value = Rate(
        rate_id=3, avg_consumption_km_l=15.0, avg_fuel_price_eur_l=1.7,
    )
    repos["registry"].generate.return_value = 500
    repos["pathtrack"].find_active_for_month.return_value = None
    repos["pathtrack"].insert.return_value = 100
    repos["doc"].insert.return_value = 1

    new_id = svc.create_fuel(
        employee_hire_history_id=10,
        full_name="Rossi Mario",
        date_path_track=date(2026, 4, 1),
        number_of_trips=20,
        sheet_pdf=b"%PDF-foglio-percorso",
        receipt_pdfs=[b"%PDF-ricevuta-1"],
    )

    assert new_id == 100
    repos["rate"].find_for_date.assert_called_once_with(date(2026, 4, 1))
    repos["registry"].generate.assert_called_once()
    insert_kwargs = repos["pathtrack"].insert.call_args.kwargs
    assert insert_kwargs["reimbursement_type"] == "CARBURANTE"
    assert insert_kwargs["computed_amount_eur"] == pytest.approx(45.33, abs=0.01)
    assert insert_kwargs["registry_id"] == 500
    # 2 documenti: 1 sheet + 1 ricevuta
    assert repos["doc"].insert.call_count == 2
    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()


def test_create_taxi_happy_path():
    svc, repos, conn = _make_service()
    repos["coordinate"].find_active.return_value = ActiveCoordinate(
        coordinate_id=99, label="Casa", lat=45.0, lon=9.0, road_km_to_workplace=10.0,
    )
    repos["pathtrack"].find_active_for_month.return_value = None
    repos["registry"].generate.return_value = 600
    repos["pathtrack"].insert.return_value = 101
    repos["doc"].insert.return_value = 5

    new_id = svc.create_taxi(
        employee_hire_history_id=10,
        full_name="Bianchi Luigi",
        date_path_track=date(2026, 4, 1),
        number_of_trips=10,
        receipt_amounts=[12.50, 8.30],
        sheet_pdf=b"%PDF-foglio",
        receipt_pdfs=[b"%PDF-r1", b"%PDF-r2"],
    )

    assert new_id == 101
    repos["rate"].find_for_date.assert_not_called()
    insert_kwargs = repos["pathtrack"].insert.call_args.kwargs
    assert insert_kwargs["reimbursement_type"] == "TAXI"
    assert insert_kwargs["rate_id_used"] is None
    assert insert_kwargs["taxi_total_eur"] == pytest.approx(20.80)
    assert insert_kwargs["computed_amount_eur"] == pytest.approx(20.80)
    assert repos["doc"].insert.call_count == 3  # 1 sheet + 2 ricevute
    conn.commit.assert_called_once()


def test_create_rolls_back_on_insert_failure():
    svc, repos, conn = _make_service()
    repos["coordinate"].find_active.return_value = ActiveCoordinate(99, "Casa", 45.0, 9.0, 10.0)
    repos["rate"].find_for_date.return_value = Rate(3, 15.0, 1.7)
    repos["registry"].generate.return_value = 500
    repos["pathtrack"].find_active_for_month.return_value = None
    repos["pathtrack"].insert.side_effect = RuntimeError("DB error")

    with pytest.raises(RuntimeError):
        svc.create_fuel(
            employee_hire_history_id=10,
            full_name="x",
            date_path_track=date(2026, 4, 1),
            number_of_trips=10,
            sheet_pdf=b"%PDF-",
            receipt_pdfs=[b"%PDF-"],
        )

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()


def test_create_raises_when_no_active_coordinate():
    svc, repos, _ = _make_service()
    repos["coordinate"].find_active.return_value = None

    with pytest.raises(NoActiveCoordinateError):
        svc.create_fuel(
            employee_hire_history_id=10,
            full_name="x",
            date_path_track=date(2026, 4, 1),
            number_of_trips=10,
            sheet_pdf=b"%PDF-",
            receipt_pdfs=[b"%PDF-"],
        )

    repos["pathtrack"].insert.assert_not_called()


def test_create_raises_when_no_rate_configured_for_fuel():
    svc, repos, _ = _make_service()
    repos["coordinate"].find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 3)
    repos["rate"].find_for_date.return_value = None

    with pytest.raises(NoRateConfiguredError):
        svc.create_fuel(
            employee_hire_history_id=10,
            full_name="x",
            date_path_track=date(2026, 4, 1),
            number_of_trips=10,
            sheet_pdf=b"%PDF-",
            receipt_pdfs=[b"%PDF-"],
        )


def test_create_raises_when_already_active_for_month():
    svc, repos, _ = _make_service()
    repos["coordinate"].find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 3)
    repos["rate"].find_for_date.return_value = Rate(3, 15.0, 1.7)
    repos["pathtrack"].find_active_for_month.return_value = PathTrackRow(
        path_track_id=999, registry_id=1, date_path_track=date(2026, 4, 1),
        declarated_path_id=99, in_behalf_of_id=None,
        reimbursement_type="CARBURANTE", number_of_trips=10, road_km=10.0,
        rate_id_used=3, taxi_total_eur=None, computed_amount_eur=10.0,
    )

    with pytest.raises(DuplicateDeclarationError):
        svc.create_fuel(
            employee_hire_history_id=10,
            full_name="x",
            date_path_track=date(2026, 4, 1),
            number_of_trips=10,
            sheet_pdf=b"%PDF-",
            receipt_pdfs=[b"%PDF-"],
        )


def test_create_fuel_validates_trips_range():
    svc, repos, _ = _make_service()
    repos["coordinate"].find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 3)

    with pytest.raises(InvalidInputError, match="viaggi"):
        svc.create_fuel(
            employee_hire_history_id=10,
            full_name="x",
            date_path_track=date(2026, 4, 1),
            number_of_trips=0,
            sheet_pdf=b"%PDF-",
            receipt_pdfs=[b"%PDF-"],
        )


def test_create_fuel_requires_at_least_one_sheet_pdf():
    svc, repos, _ = _make_service()
    repos["coordinate"].find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 3)

    with pytest.raises(InvalidInputError, match="foglio"):
        svc.create_fuel(
            employee_hire_history_id=10,
            full_name="x",
            date_path_track=date(2026, 4, 1),
            number_of_trips=10,
            sheet_pdf=None,
            receipt_pdfs=[b"%PDF-"],
        )


def test_create_taxi_requires_at_least_one_receipt():
    svc, repos, _ = _make_service()
    repos["coordinate"].find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 3)

    with pytest.raises(InvalidInputError, match="ricevuta"):
        svc.create_taxi(
            employee_hire_history_id=10,
            full_name="x",
            date_path_track=date(2026, 4, 1),
            number_of_trips=10,
            receipt_amounts=[],
            sheet_pdf=b"%PDF-",
            receipt_pdfs=[],
        )
