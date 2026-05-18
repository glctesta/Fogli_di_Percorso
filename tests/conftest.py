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
    app = create_app(settings=TestSettings, db=mock_db)
    yield app


@pytest.fixture
def client(app):
    return app.test_client()
