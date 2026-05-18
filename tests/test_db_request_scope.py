"""Verifica che Database fornisca connessioni per-request via flask.g."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, g

from fdp_app.db import Database, get_request_db, teardown_request_db


def _build_app_with_db(db):
    app = Flask(__name__)
    app.config["_db"] = db
    app.teardown_appcontext(teardown_request_db)

    @app.route("/probe")
    def probe():
        conn1 = get_request_db()
        conn2 = get_request_db()
        # Stessa request -> stessa connection
        assert conn1 is conn2
        return {"ok": True}

    return app


def test_same_request_reuses_one_connection():
    db = MagicMock(spec=Database)
    db.connect.return_value = MagicMock(name="conn1")
    app = _build_app_with_db(db)
    client = app.test_client()

    response = client.get("/probe")
    assert response.status_code == 200
    # Una sola request: connect() chiamato una sola volta
    assert db.connect.call_count == 1


def test_different_requests_get_different_connections():
    db = MagicMock(spec=Database)
    db.connect.side_effect = [
        MagicMock(name="conn1"),
        MagicMock(name="conn2"),
    ]
    app = _build_app_with_db(db)
    client = app.test_client()

    r1 = client.get("/probe")
    r2 = client.get("/probe")
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Due request -> due connect()
    assert db.connect.call_count == 2


def test_teardown_closes_request_connection():
    db = MagicMock(spec=Database)
    real_conn = MagicMock(name="real_conn")
    db.connect.return_value = real_conn
    app = _build_app_with_db(db)
    client = app.test_client()

    client.get("/probe")
    real_conn.close.assert_called_once()
