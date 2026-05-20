"""Configurazione applicativa (non segreti)."""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    """Settings letti da env var (con default) o file di configurazione."""

    # Flask
    SECRET_KEY: str = os.environ.get("FDP_SECRET_KEY") or secrets.token_hex(32)
    WTF_CSRF_ENABLED: bool = True
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"
    SESSION_COOKIE_SECURE: bool = os.environ.get("FDP_COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME: int = 8 * 60 * 60  # 8 ore in secondi

    # Routing
    OSRM_BASE: str = os.environ.get(
        "FDP_OSRM_BASE", "https://router.project-osrm.org"
    )
    ORS_API_KEY: str | None = os.environ.get("FDP_ORS_API_KEY")
    ORS_BASE: str = "https://api.openrouteservice.org"

    # Geocoding inverso
    NOMINATIM_BASE: str = "https://nominatim.openstreetmap.org"
    NOMINATIM_USER_AGENT: str = "FogliDiPercorso/1.0 (intranet)"

    # App
    APP_URL: str = os.environ.get("FDP_APP_URL", "http://localhost:5010")
    EMPLOYER_ID: int = 2
    MIN_FUNCTION_CODE_FOR_LOGIN: int = 60  # esclusivo: serve > 60
    REGISTRY_TYPE_ID: int = 790

    # Workplace
    @classmethod
    def workplace(cls) -> dict:
        with open(BASE_DIR / "config" / "workplace.json", encoding="utf-8") as f:
            return json.load(f)

    # Rate limit login
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_WINDOW_SECONDS: int = 15 * 60

    # Upload PDF
    UPLOAD_MAX_BYTES: int = 5 * 1024 * 1024
    UPLOAD_MAX_FILES_PER_PATHTRACK: int = 20

    # Flask MAX_CONTENT_LENGTH: rifiuta richieste piu' grandi PRIMA di leggere i file
    # (max_files + 1) * max_bytes per il sheet + tutte le ricevute
    MAX_CONTENT_LENGTH: int = (
        UPLOAD_MAX_BYTES * (UPLOAD_MAX_FILES_PER_PATHTRACK + 1)
    )

    # i18n / Babel
    LANGUAGES: tuple = ("ro", "it", "en")
    BABEL_DEFAULT_LOCALE: str = "ro"
    BABEL_DEFAULT_TIMEZONE: str = "Europe/Rome"
    LANGUAGE_COOKIE_NAME: str = "fdp_lang"
    LANGUAGE_COOKIE_MAX_AGE: int = 365 * 24 * 3600
