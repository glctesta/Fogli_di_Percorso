"""Database con per-request connection via flask.g."""
from __future__ import annotations

from typing import Optional

from flask import current_app, g, has_app_context

from config_manager import ConfigManager
from db_connection import DatabaseConnection


class Database:
    """Wrapper iniettabile: usa DatabaseConnection legacy per costruire
    nuove connessioni `pyodbc`. Il lifecycle e' gestito da flask.g
    (vedi `get_request_db` e `teardown_request_db`).
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None) -> None:
        self._cm = config_manager or ConfigManager()

    def connect(self):
        """Crea una NUOVA pyodbc.Connection. Non e' cached qui."""
        dc = DatabaseConnection(self._cm)
        return dc.connect()


def get_request_db():
    """Ritorna la connection associata alla request corrente.

    Crea e cacha su flask.g al primo accesso. La connection sara' chiusa
    da `teardown_request_db` al termine della request.
    """
    if not has_app_context():
        raise RuntimeError("get_request_db chiamato fuori da una request")
    if "db_conn" not in g:
        db: Database = current_app.config["_db"]
        g.db_conn = db.connect()
    return g.db_conn


def teardown_request_db(exception):
    """Da registrare con app.teardown_appcontext. Chiude la connection."""
    conn = g.pop("db_conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
