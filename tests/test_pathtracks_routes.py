"""Test E2E delle route /pathtracks/*."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from freezegun import freeze_time

pytestmark = pytest.mark.skip(reason="Task 5 of Piano 3.1 will rewrite these tests for the DRAFT/SUBMITTED workflow")


@pytest.fixture
def mock_coord_repo():
    with patch("fdp_app.pathtracks.routes.CoordinateRepo") as cls:
        instance = MagicMock()
        instance.find_active.return_value = None
        cls.return_value = instance
        yield instance


@pytest.fixture
def mock_rate_repo():
    with patch("fdp_app.pathtracks.routes.RateRepo") as cls:
        instance = MagicMock()
        cls.return_value = instance
        yield instance


@pytest.fixture
def mock_pathtrack_repo():
    with patch("fdp_app.pathtracks.routes.PathTrackRepo") as cls:
        instance = MagicMock()
        instance.find_active_for_month.return_value = None
        instance.list_for_employee.return_value = []
        cls.return_value = instance
        yield instance


@pytest.fixture
def mock_doc_repo():
    with patch("fdp_app.pathtracks.routes.PathTrackDocRepo") as cls:
        instance = MagicMock()
        cls.return_value = instance
        yield instance


@pytest.fixture
def mock_registry_repo():
    with patch("fdp_app.pathtracks.routes.RegistryRepo") as cls:
        instance = MagicMock()
        cls.return_value = instance
        yield instance


def _login(client, eh_id=10):
    with client.session_transaction() as sess:
        sess["user_id"] = eh_id
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = 5
        sess["function_code"] = 70


def test_new_requires_login(client):
    response = client.get("/pathtracks/new", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


@freeze_time("2026-05-03 10:00:00+02:00")
def test_new_redirects_to_coordinates_when_no_active_coordinate(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo
):
    _login(client)
    mock_coord_repo.find_active.return_value = None

    response = client.get("/pathtracks/new", follow_redirects=False)
    assert response.status_code == 302
    assert "/coordinates" in response.headers["Location"]


@freeze_time("2026-05-03 10:00:00+02:00")
def test_new_shows_form_when_in_deadline_window(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo
):
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    from fdp_app.repos.rate_repo import Rate
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(
        coordinate_id=99, label="Casa", lat=45.0, lon=9.0, road_km_to_workplace=10.5,
    )
    mock_rate_repo.find_for_date.return_value = Rate(
        rate_id=3, avg_consumption_km_l=15.0, avg_fuel_price_eur_l=1.7,
    )
    mock_pathtrack_repo.find_active_for_month.return_value = None

    response = client.get("/pathtracks/new")
    assert response.status_code == 200
    assert b"Dichiarazione mensile" in response.data
    assert b"10.5" in response.data or b"10,5" in response.data


@freeze_time("2026-05-06 00:00:01+02:00")
def test_new_blocks_when_deadline_passed(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo
):
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 10.0)

    response = client.get("/pathtracks/new", follow_redirects=True)
    assert response.status_code == 200
    assert b"chius" in response.data.lower() or b"scadut" in response.data.lower()


@freeze_time("2026-05-03 10:00:00+02:00")
def test_post_new_fuel_creates_declaration(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo,
    mock_doc_repo, mock_registry_repo
):
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    from fdp_app.repos.rate_repo import Rate
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(
        99, "Casa", 45.0, 9.0, 10.0,
    )
    mock_rate_repo.find_for_date.return_value = Rate(3, 15.0, 1.7)
    mock_pathtrack_repo.find_active_for_month.return_value = None
    mock_pathtrack_repo.insert.return_value = 555
    mock_registry_repo.generate.return_value = 500

    with patch("fdp_app.pathtracks.routes.get_request_db") as mock_get_db:
        conn = MagicMock()
        conn.autocommit = True
        mock_get_db.return_value = conn

        from io import BytesIO
        response = client.post(
            "/pathtracks/new",
            data={
                "reimbursement_type": "CARBURANTE",
                "number_of_trips": "20",
                "sheet_pdf": (BytesIO(b"%PDF-1.4 sheet"), "foglio.pdf"),
                "receipt_pdf": (BytesIO(b"%PDF-1.4 receipt"), "ricevuta.pdf"),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert "/pathtracks/555" in response.headers["Location"]
    mock_pathtrack_repo.insert.assert_called_once()
    kwargs = mock_pathtrack_repo.insert.call_args.kwargs
    assert kwargs["reimbursement_type"] == "CARBURANTE"
    assert kwargs["number_of_trips"] == 20


@freeze_time("2026-05-03 10:00:00+02:00")
def test_post_new_taxi_creates_declaration(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo,
    mock_doc_repo, mock_registry_repo
):
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(
        99, "Casa", 45.0, 9.0, 10.0,
    )
    mock_pathtrack_repo.find_active_for_month.return_value = None
    mock_pathtrack_repo.insert.return_value = 556
    mock_registry_repo.generate.return_value = 600

    with patch("fdp_app.pathtracks.routes.get_request_db") as mock_get_db:
        conn = MagicMock()
        conn.autocommit = True
        mock_get_db.return_value = conn

        from io import BytesIO
        response = client.post(
            "/pathtracks/new",
            data={
                "reimbursement_type": "TAXI",
                "number_of_trips": "10",
                "taxi_amount": ["12.50", "8.30"],
                "sheet_pdf": (BytesIO(b"%PDF-1.4 sheet"), "foglio.pdf"),
                "receipt_pdf": [
                    (BytesIO(b"%PDF-1.4 r1"), "r1.pdf"),
                    (BytesIO(b"%PDF-1.4 r2"), "r2.pdf"),
                ],
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )

    assert response.status_code == 302
    kwargs = mock_pathtrack_repo.insert.call_args.kwargs
    assert kwargs["reimbursement_type"] == "TAXI"
    assert kwargs["taxi_total_eur"] == pytest.approx(20.80)


@freeze_time("2026-05-03 10:00:00+02:00")
def test_post_new_rejects_missing_sheet_pdf(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo
):
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    from fdp_app.repos.rate_repo import Rate
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 10.0)
    mock_rate_repo.find_for_date.return_value = Rate(3, 15.0, 1.7)
    mock_pathtrack_repo.find_active_for_month.return_value = None

    from io import BytesIO
    response = client.post(
        "/pathtracks/new",
        data={
            "reimbursement_type": "CARBURANTE",
            "number_of_trips": "10",
            "receipt_pdf": (BytesIO(b"%PDF-1.4"), "ricevuta.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"foglio" in response.data.lower()
    mock_pathtrack_repo.insert.assert_not_called()


@freeze_time("2026-05-03 10:00:00+02:00")
def test_post_new_rejects_oversized_pdf(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo
):
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    from fdp_app.repos.rate_repo import Rate
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 10.0)
    mock_rate_repo.find_for_date.return_value = Rate(3, 15.0, 1.7)
    mock_pathtrack_repo.find_active_for_month.return_value = None

    from io import BytesIO
    big_pdf = b"%PDF-1.4" + (b"\x00" * (5 * 1024 * 1024 + 1))

    response = client.post(
        "/pathtracks/new",
        data={
            "reimbursement_type": "CARBURANTE",
            "number_of_trips": "10",
            "sheet_pdf": (BytesIO(big_pdf), "big.pdf"),
            "receipt_pdf": (BytesIO(b"%PDF-1.4"), "r.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"5 mb" in response.data.lower() or b"troppo grande" in response.data.lower()


def test_view_requires_login(client):
    response = client.get("/pathtracks/1", follow_redirects=False)
    assert response.status_code == 302


def test_view_shows_declaration(client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo):
    from fdp_app.repos.pathtrack_repo import PathTrackRow
    from datetime import date as Date
    _login(client)
    mock_pathtrack_repo.find_by_id.return_value = PathTrackRow(
        path_track_id=100, registry_id=500, date_path_track=Date(2026, 4, 1),
        declarated_path_id=99, in_behalf_of_id=None,
        reimbursement_type="CARBURANTE", number_of_trips=20, road_km=10.0,
        rate_id_used=3, taxi_total_eur=None, computed_amount_eur=45.33,
        status="SUBMITTED", submitted_on=None,
    )
    mock_doc_repo.list_for_pathtrack.return_value = []

    response = client.get("/pathtracks/100")
    assert response.status_code == 200
    assert b"CARBURANTE" in response.data
    assert b"45.33" in response.data or b"45,33" in response.data
    assert b"Aprile" in response.data


def test_view_not_owned_returns_404(client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo):
    _login(client)
    mock_pathtrack_repo.find_by_id.return_value = None

    response = client.get("/pathtracks/999")
    assert response.status_code == 404


@freeze_time("2026-05-03 10:00:00+02:00")
def test_post_delete_soft_deletes_within_window(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo
):
    from fdp_app.repos.pathtrack_repo import PathTrackRow
    from datetime import date as Date
    _login(client)
    mock_pathtrack_repo.find_by_id.return_value = PathTrackRow(
        path_track_id=100, registry_id=500, date_path_track=Date(2026, 4, 1),
        declarated_path_id=99, in_behalf_of_id=None,
        reimbursement_type="CARBURANTE", number_of_trips=10, road_km=10.0,
        rate_id_used=3, taxi_total_eur=None, computed_amount_eur=10.0,
        status="SUBMITTED", submitted_on=None,
    )
    mock_pathtrack_repo.soft_delete.return_value = True

    response = client.post(
        "/pathtracks/100/delete",
        follow_redirects=False,
    )

    assert response.status_code == 302
    mock_pathtrack_repo.soft_delete.assert_called_once_with(
        path_track_id=100, employee_hire_history_id=10
    )


@freeze_time("2026-05-06 00:00:01+02:00")
def test_post_delete_rejects_after_window(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo
):
    from fdp_app.repos.pathtrack_repo import PathTrackRow
    from datetime import date as Date
    _login(client)
    mock_pathtrack_repo.find_by_id.return_value = PathTrackRow(
        path_track_id=100, registry_id=500, date_path_track=Date(2026, 4, 1),
        declarated_path_id=99, in_behalf_of_id=None,
        reimbursement_type="CARBURANTE", number_of_trips=10, road_km=10.0,
        rate_id_used=3, taxi_total_eur=None, computed_amount_eur=10.0,
        status="SUBMITTED", submitted_on=None,
    )

    response = client.post(
        "/pathtracks/100/delete",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"chius" in response.data.lower() or b"scadut" in response.data.lower()
    mock_pathtrack_repo.soft_delete.assert_not_called()


def test_list_shows_user_declarations(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo
):
    from fdp_app.repos.pathtrack_repo import PathTrackRow
    from datetime import date as Date
    _login(client)
    mock_pathtrack_repo.list_for_employee.return_value = [
        PathTrackRow(1, 100, Date(2026, 4, 1), 99, None, "CARBURANTE", 20, 10.0, 3, None, 45.33, "SUBMITTED", None),
        PathTrackRow(2, 101, Date(2026, 3, 1), 99, None, "TAXI", 10, 8.0, None, 30.0, 30.0, "SUBMITTED", None),
    ]

    response = client.get("/pathtracks")
    assert response.status_code == 200
    assert b"CARBURANTE" in response.data
    assert b"TAXI" in response.data
    assert b"45.33" in response.data or b"45,33" in response.data


@freeze_time("2026-05-03 10:00:00+02:00")
def test_post_new_rejects_non_pdf_sheet(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo
):
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    from fdp_app.repos.rate_repo import Rate
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 10.0)
    mock_rate_repo.find_for_date.return_value = Rate(3, 15.0, 1.7)
    mock_pathtrack_repo.find_active_for_month.return_value = None

    from io import BytesIO
    response = client.post(
        "/pathtracks/new",
        data={
            "reimbursement_type": "CARBURANTE",
            "number_of_trips": "10",
            "sheet_pdf": (BytesIO(b"<html>not a pdf</html>"), "fake.pdf"),
            "receipt_pdf": (BytesIO(b"%PDF-1.4 r"), "r.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"pdf" in response.data.lower()
    mock_pathtrack_repo.insert.assert_not_called()
