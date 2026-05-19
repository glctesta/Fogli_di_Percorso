"""Test E2E delle route /pathtracks/* (workflow DRAFT/SUBMITTED)."""
from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest
from freezegun import freeze_time

from fdp_app.repos.pathtrack_repo import PathTrackRow


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
        instance.find_by_id.return_value = None
        instance.list_for_employee.return_value = []
        cls.return_value = instance
        yield instance


@pytest.fixture
def mock_doc_repo():
    with patch("fdp_app.pathtracks.routes.PathTrackDocRepo") as cls:
        instance = MagicMock()
        instance.list_for_pathtrack.return_value = []
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


def _row(status="DRAFT", date_path_track=None, path_track_id=100):
    return PathTrackRow(
        path_track_id=path_track_id,
        registry_id=None if status == "DRAFT" else 500,
        date_path_track=date_path_track or date(2026, 5, 1),
        declarated_path_id=99,
        in_behalf_of_id=None,
        reimbursement_type="CARBURANTE",
        number_of_trips=10,
        road_km=10.0,
        rate_id_used=3,
        taxi_total_eur=None,
        computed_amount_eur=53.55,
        status=status,
        submitted_on=None if status == "DRAFT" else datetime(2026, 5, 3, 10, 0),
    )


# ---- GET /new --------------------------------------------------------------

def test_new_requires_login(client):
    response = client.get("/pathtracks/new", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


@freeze_time("2026-05-15 10:00:00+02:00")
def test_new_redirects_to_coordinates_when_no_active_coordinate(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo
):
    _login(client)
    mock_coord_repo.find_active.return_value = None

    response = client.get("/pathtracks/new", follow_redirects=False)
    assert response.status_code == 302
    assert "/coordinates" in response.headers["Location"]


@freeze_time("2026-05-15 10:00:00+02:00")
def test_new_shows_form_for_current_month_in_anticipo(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo
):
    """Il 15 maggio posso lavorare alla bozza di maggio (in anticipo)."""
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    from fdp_app.repos.rate_repo import Rate
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(
        coordinate_id=99, label="Casa", lat=45.0, lon=9.0, road_km_to_workplace=10.5,
    )
    mock_rate_repo.find_for_date.return_value = Rate(3, 15.0, 1.7)
    mock_pathtrack_repo.find_active_for_month.return_value = None

    response = client.get("/pathtracks/new")
    assert response.status_code == 200
    # Submit button disabled mid-month (no submit window)
    assert b"Salva bozza" in response.data
    assert b"dal 1 al 5 del mese successivo" in response.data.lower() or b"disponibile dal" in response.data.lower()


@freeze_time("2026-05-03 10:00:00+02:00")
def test_new_shows_form_with_active_submit_button_within_window(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo
):
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    from fdp_app.repos.rate_repo import Rate
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(
        coordinate_id=99, label="Casa", lat=45.0, lon=9.0, road_km_to_workplace=10.5,
    )
    mock_rate_repo.find_for_date.return_value = Rate(3, 15.0, 1.7)
    mock_pathtrack_repo.find_active_for_month.return_value = None

    response = client.get("/pathtracks/new")
    assert response.status_code == 200
    assert b"Salva bozza" in response.data
    assert b"Salva e invia" in response.data


# ---- POST /new (draft) -----------------------------------------------------

@freeze_time("2026-05-15 10:00:00+02:00")
def test_post_new_saves_draft_for_current_month(
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

    with patch("fdp_app.pathtracks.routes.get_request_db") as mock_get_db:
        conn = MagicMock()
        conn.autocommit = True
        mock_get_db.return_value = conn

        from io import BytesIO
        response = client.post(
            "/pathtracks/new",
            data={
                "action": "draft",
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
    insert_kwargs = mock_pathtrack_repo.insert.call_args.kwargs
    assert insert_kwargs["status"] == "DRAFT"
    assert insert_kwargs["registry_id"] is None
    # No SP call for draft
    mock_registry_repo.generate.assert_not_called()


# ---- POST /new with action=submit ------------------------------------------

@freeze_time("2026-05-03 10:00:00+02:00")
def test_post_new_save_and_submit_in_window(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo,
    mock_doc_repo, mock_registry_repo
):
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    from fdp_app.repos.rate_repo import Rate
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(99, "Casa", 45.0, 9.0, 10.0)
    mock_rate_repo.find_for_date.return_value = Rate(3, 15.0, 1.7)
    mock_pathtrack_repo.find_active_for_month.return_value = None
    mock_pathtrack_repo.insert.return_value = 555
    # After insert, find_by_id should return the freshly inserted draft for submit
    mock_pathtrack_repo.find_by_id.return_value = _row(status="DRAFT", date_path_track=date(2026, 4, 1), path_track_id=555)
    mock_registry_repo.generate.return_value = 700
    mock_pathtrack_repo.mark_as_submitted.return_value = True

    with patch("fdp_app.pathtracks.routes.get_request_db") as mock_get_db:
        conn = MagicMock()
        conn.autocommit = True
        mock_get_db.return_value = conn

        from io import BytesIO
        response = client.post(
            "/pathtracks/new",
            data={
                "action": "submit",
                "reimbursement_type": "CARBURANTE",
                "number_of_trips": "20",
                "sheet_pdf": (BytesIO(b"%PDF-1.4 sheet"), "foglio.pdf"),
                "receipt_pdf": (BytesIO(b"%PDF-1.4 r"), "r.pdf"),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )

    assert response.status_code == 302
    mock_registry_repo.generate.assert_called_once()
    mock_pathtrack_repo.mark_as_submitted.assert_called_once()


# ---- POST /<id>/submit ----------------------------------------------------

@freeze_time("2026-05-03 10:00:00+02:00")
def test_post_submit_endpoint_marks_draft_as_submitted(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo,
    mock_doc_repo, mock_registry_repo
):
    _login(client)
    mock_pathtrack_repo.find_by_id.return_value = _row(
        status="DRAFT", date_path_track=date(2026, 4, 1), path_track_id=100,
    )
    mock_registry_repo.generate.return_value = 800
    mock_pathtrack_repo.mark_as_submitted.return_value = True

    with patch("fdp_app.pathtracks.routes.get_request_db") as mock_get_db:
        conn = MagicMock()
        conn.autocommit = True
        mock_get_db.return_value = conn

        response = client.post("/pathtracks/100/submit", follow_redirects=False)

    assert response.status_code == 302
    mock_registry_repo.generate.assert_called_once_with(issued_by_full_name="Rossi Mario")
    mock_pathtrack_repo.mark_as_submitted.assert_called_once_with(
        path_track_id=100, employee_hire_history_id=10, registry_id=800,
    )


@freeze_time("2026-05-15 10:00:00+02:00")
def test_post_submit_rejected_outside_window(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo
):
    _login(client)
    mock_pathtrack_repo.find_by_id.return_value = _row(
        status="DRAFT", date_path_track=date(2026, 4, 1), path_track_id=100,
    )

    response = client.post("/pathtracks/100/submit", follow_redirects=True)
    assert response.status_code == 200
    mock_registry_repo.generate.assert_not_called()
    mock_pathtrack_repo.mark_as_submitted.assert_not_called()


# ---- GET /<id> view --------------------------------------------------------

def test_view_requires_login(client):
    response = client.get("/pathtracks/1", follow_redirects=False)
    assert response.status_code == 302


@freeze_time("2026-05-03 10:00:00+02:00")
def test_view_shows_draft_with_edit_form(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo
):
    _login(client)
    mock_pathtrack_repo.find_by_id.return_value = _row(status="DRAFT", date_path_track=date(2026, 4, 1))
    mock_doc_repo.list_for_pathtrack.return_value = []
    from fdp_app.repos.rate_repo import Rate
    mock_rate_repo.find_for_date.return_value = Rate(3, 15.0, 1.7)

    response = client.get("/pathtracks/100")
    assert response.status_code == 200
    assert b"BOZZA" in response.data
    assert b"Modifica bozza" in response.data
    assert b"Conferma e invia" in response.data


@freeze_time("2026-05-15 10:00:00+02:00")
def test_view_shows_submitted_readonly(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo
):
    _login(client)
    mock_pathtrack_repo.find_by_id.return_value = _row(status="SUBMITTED", date_path_track=date(2026, 4, 1))
    mock_doc_repo.list_for_pathtrack.return_value = []

    response = client.get("/pathtracks/100")
    assert response.status_code == 200
    assert b"INVIATA" in response.data
    assert b"Modifica bozza" not in response.data


def test_view_not_owned_returns_404(client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo):
    _login(client)
    mock_pathtrack_repo.find_by_id.return_value = None
    response = client.get("/pathtracks/999")
    assert response.status_code == 404


# ---- POST /<id>/update ----------------------------------------------------

@freeze_time("2026-05-03 10:00:00+02:00")
def test_post_update_modifies_draft(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo
):
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    from fdp_app.repos.rate_repo import Rate
    _login(client)
    mock_pathtrack_repo.find_by_id.return_value = _row(status="DRAFT", date_path_track=date(2026, 4, 1))
    mock_coord_repo.find_active.return_value = ActiveCoordinate(99, "Casa", 45.0, 9.0, 12.0)
    mock_rate_repo.find_for_date.return_value = Rate(3, 15.0, 1.7)

    with patch("fdp_app.pathtracks.routes.get_request_db") as mock_get_db:
        conn = MagicMock()
        conn.autocommit = True
        mock_get_db.return_value = conn

        from io import BytesIO
        response = client.post(
            "/pathtracks/100/update",
            data={
                "reimbursement_type": "CARBURANTE",
                "number_of_trips": "25",
                "sheet_pdf": (BytesIO(b"%PDF-1.4"), "foglio.pdf"),
                "receipt_pdf": (BytesIO(b"%PDF-1.4"), "r.pdf"),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )

    assert response.status_code == 302
    mock_pathtrack_repo.update_draft.assert_called_once()


# ---- POST /<id>/delete ----------------------------------------------------

@freeze_time("2026-05-03 10:00:00+02:00")
def test_post_delete_soft_deletes_draft(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo
):
    _login(client)
    mock_pathtrack_repo.find_by_id.return_value = _row(status="DRAFT", date_path_track=date(2026, 4, 1))
    mock_pathtrack_repo.soft_delete.return_value = True

    response = client.post("/pathtracks/100/delete", follow_redirects=False)
    assert response.status_code == 302
    mock_pathtrack_repo.soft_delete.assert_called_once_with(
        path_track_id=100, employee_hire_history_id=10,
    )


@freeze_time("2026-05-03 10:00:00+02:00")
def test_post_delete_rejected_for_submitted(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo
):
    _login(client)
    mock_pathtrack_repo.find_by_id.return_value = _row(status="SUBMITTED", date_path_track=date(2026, 4, 1))

    response = client.post("/pathtracks/100/delete", follow_redirects=True)
    assert response.status_code == 200
    mock_pathtrack_repo.soft_delete.assert_not_called()


# ---- GET / list ------------------------------------------------------------

def test_list_shows_user_declarations_with_status(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo
):
    _login(client)
    mock_pathtrack_repo.list_for_employee.return_value = [
        _row(status="DRAFT", date_path_track=date(2026, 5, 1), path_track_id=1),
        _row(status="SUBMITTED", date_path_track=date(2026, 4, 1), path_track_id=2),
    ]

    response = client.get("/pathtracks")
    assert response.status_code == 200
    assert b"BOZZA" in response.data
    assert b"INVIATA" in response.data
