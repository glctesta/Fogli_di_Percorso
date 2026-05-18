"""Fixture condivise pytest."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from config.settings import Settings
from fdp_app import create_app
from fdp_app.db import Database


class TestSettings(Settings):
    TESTING = True
    SECRET_KEY = "test-secret-key-only-for-pytest"
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False


@pytest.fixture
def mock_db():
    db = MagicMock(spec=Database)
    return db


@pytest.fixture
def app(mock_db):
    application = create_app(settings=TestSettings, db=mock_db)
    yield application
    # Chiude i file handler attaccati a app.logger per evitare leak
    for handler in list(application.logger.handlers):
        try:
            handler.close()
        except Exception:
            pass
        application.logger.removeHandler(handler)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset del singleton rate_limiter tra ogni test per evitare inquinamento."""
    import fdp_app.auth.routes as auth_routes
    auth_routes._rate_limiter = None
    yield
    auth_routes._rate_limiter = None
