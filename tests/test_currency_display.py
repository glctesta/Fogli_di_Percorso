"""Test the eur_with_ron Jinja filter."""
from __future__ import annotations

import pytest


def test_eur_only_when_no_rate(app):
    with app.test_request_context("/"):
        fn = app.jinja_env.filters["eur_with_ron"]
        result = str(fn(45.33, None))
        assert "45.33" in result
        assert "RON" not in result


def test_eur_with_ron_when_rate_given(app):
    with app.test_request_context("/"):
        fn = app.jinja_env.filters["eur_with_ron"]
        result = str(fn(45.33, 4.9756))
        assert "45.33" in result
        assert "RON" in result
        # 45.33 * 4.9756 = 225.51... (close)
        # The exact format depends on the formula; just check the integer part
        assert "225" in result
        assert "4.9756" in result


def test_eur_with_zero_rate_falls_back_to_eur_only(app):
    with app.test_request_context("/"):
        fn = app.jinja_env.filters["eur_with_ron"]
        result = str(fn(10.0, 0))
        assert "RON" not in result


def test_eur_with_none_amount_returns_empty(app):
    with app.test_request_context("/"):
        fn = app.jinja_env.filters["eur_with_ron"]
        result = str(fn(None, 4.97))
        assert result == ""


def test_pathtracks_view_shows_ron_when_rate_is_set(client):
    from unittest.mock import patch, MagicMock
    from fdp_app.repos.pathtrack_repo import PathTrackRow
    from datetime import date as Date, datetime as DT

    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = 5
        sess["function_code"] = 70

    with patch("fdp_app.pathtracks.routes.PathTrackRepo") as pt_cls, \
         patch("fdp_app.pathtracks.routes.PathTrackDocRepo") as doc_cls, \
         patch("fdp_app.pathtracks.routes.RateRepo") as rate_cls:
        pt = MagicMock()
        pt.find_by_id.return_value = PathTrackRow(
            path_track_id=100, registry_id=500, date_path_track=Date(2026, 4, 1),
            declarated_path_id=99, in_behalf_of_id=None,
            reimbursement_type="CARBURANTE", number_of_trips=20, road_km=10.0,
            rate_id_used=3, taxi_total_eur=None, computed_amount_eur=45.33,
            status="SUBMITTED", submitted_on=DT(2026, 5, 3, 10, 0),
            bnr_rate_ron_per_eur=4.9756,
        )
        pt_cls.return_value = pt
        doc = MagicMock()
        doc.list_for_pathtrack.return_value = []
        doc_cls.return_value = doc
        rate = MagicMock()
        rate.find_for_date.return_value = None
        rate_cls.return_value = rate
        response = client.get("/pathtracks/100")
    assert response.status_code == 200
    assert b"45.33" in response.data
    assert b"RON" in response.data
    assert b"4.9756" in response.data


def test_pathtracks_view_no_ron_when_rate_is_none(client):
    from unittest.mock import patch, MagicMock
    from fdp_app.repos.pathtrack_repo import PathTrackRow
    from fdp_app.repos.rate_repo import Rate
    from datetime import date as Date

    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = 5
        sess["function_code"] = 70

    with patch("fdp_app.pathtracks.routes.PathTrackRepo") as pt_cls, \
         patch("fdp_app.pathtracks.routes.PathTrackDocRepo") as doc_cls, \
         patch("fdp_app.pathtracks.routes.RateRepo") as rate_cls:
        pt = MagicMock()
        pt.find_by_id.return_value = PathTrackRow(
            path_track_id=100, registry_id=None, date_path_track=Date(2026, 5, 1),
            declarated_path_id=99, in_behalf_of_id=None,
            reimbursement_type="CARBURANTE", number_of_trips=20, road_km=10.0,
            rate_id_used=3, taxi_total_eur=None, computed_amount_eur=45.33,
            status="DRAFT", submitted_on=None,
            bnr_rate_ron_per_eur=None,
        )
        pt_cls.return_value = pt
        doc = MagicMock()
        doc.list_for_pathtrack.return_value = []
        doc_cls.return_value = doc
        rate = MagicMock()
        rate.find_for_date.return_value = Rate(3, 15.0, 1.7)
        rate_cls.return_value = rate
        response = client.get("/pathtracks/100")
    assert response.status_code == 200
    assert b"45.33" in response.data
    # Should NOT contain the rate suffix when no BNR rate is stored
    assert b"tasso" not in response.data.lower()
