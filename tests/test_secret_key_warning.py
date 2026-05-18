"""Verifica che l'app emetta un warning se FDP_SECRET_KEY non e' settata in produzione."""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from config.settings import Settings
from fdp_app import create_app
from fdp_app.db import Database


def test_no_warning_when_secret_key_env_var_set(monkeypatch, caplog):
    monkeypatch.setenv("FDP_SECRET_KEY", "explicit-key-from-env-very-long-string-1234567890")
    monkeypatch.delenv("TESTING", raising=False)

    # Forziamo Settings a rileggere SECRET_KEY (era valutato al class-body load)
    class ProdSettings(Settings):
        TESTING = False
        SECRET_KEY = os.environ.get("FDP_SECRET_KEY") or "fallback"

    with caplog.at_level("WARNING"):
        create_app(settings=ProdSettings, db=MagicMock(spec=Database))

    assert "FDP_SECRET_KEY" not in caplog.text


def test_warning_emitted_when_secret_key_env_var_missing(monkeypatch, caplog):
    monkeypatch.delenv("FDP_SECRET_KEY", raising=False)

    class ProdSettings(Settings):
        TESTING = False
        # Simula il fallback: nessuna env var -> chiave ephemeral
        SECRET_KEY = "ephemeral-fallback-do-not-use-in-prod"

    with caplog.at_level("WARNING"):
        create_app(settings=ProdSettings, db=MagicMock(spec=Database))

    assert "FDP_SECRET_KEY" in caplog.text
    assert "non e' impostata" in caplog.text.lower() or "not set" in caplog.text.lower()


def test_no_warning_in_testing_mode_when_secret_key_missing(monkeypatch, caplog):
    """In TESTING mode il warning NON viene emesso anche se FDP_SECRET_KEY manca."""
    monkeypatch.delenv("FDP_SECRET_KEY", raising=False)

    from config.settings import Settings

    class TestSettingsLocal(Settings):
        TESTING = True
        SECRET_KEY = "test-secret"

    with caplog.at_level("WARNING"):
        create_app(settings=TestSettingsLocal, db=MagicMock(spec=Database))

    assert "FDP_SECRET_KEY" not in caplog.text
