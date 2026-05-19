"""Base class for repositories: shared cursor management.

Production: uses flask.g per-request connection via get_request_db().
Test: falls back to self._db.cursor() (the MagicMock injected in unit tests).
"""
from __future__ import annotations

from flask import has_app_context


class BaseRepo:
    """Mixin/base for repo classes that need cursor access."""

    def __init__(self, db) -> None:
        self._db = db

    def _open_cursor(self):
        if has_app_context():
            from fdp_app.db import get_request_db
            return get_request_db().cursor()
        return self._db.cursor()
