"""Verifica che RoutingClient sia istanziato una sola volta a startup."""
from __future__ import annotations

from unittest.mock import MagicMock

from config.settings import Settings
from fdp_app import create_app
from fdp_app.db import Database
from fdp_app.pathtracks.routing import RoutingClient


def test_routing_client_stored_in_app_config():
    class S(Settings):
        TESTING = True
        SECRET_KEY = "test"
        WTF_CSRF_ENABLED = False

    app = create_app(settings=S, db=MagicMock(spec=Database))
    assert isinstance(app.config["_routing"], RoutingClient)


def test_workplace_dict_stored_in_app_config():
    class S(Settings):
        TESTING = True
        SECRET_KEY = "test"
        WTF_CSRF_ENABLED = False

    app = create_app(settings=S, db=MagicMock(spec=Database))
    wp = app.config["_workplace"]
    assert "lat" in wp
    assert "lon" in wp
    assert "name" in wp


def test_routing_client_is_singleton_per_app():
    class S(Settings):
        TESTING = True
        SECRET_KEY = "test"
        WTF_CSRF_ENABLED = False

    app = create_app(settings=S, db=MagicMock(spec=Database))
    r1 = app.config["_routing"]
    r2 = app.config["_routing"]
    assert r1 is r2
