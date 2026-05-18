"""Wrapper attorno a db_connection.DatabaseConnection per dependency injection."""
from __future__ import annotations

import threading
from typing import Optional

from config_manager import ConfigManager
from db_connection import DatabaseConnection


class Database:
    """Wrapper iniettabile: in produzione delega a DatabaseConnection esistente.

    In test viene sostituito con MagicMock.

    Thread safety: pyodbc.Connection NON e' condivisibile fra thread.
    `cursor()` e' protetto da un Lock; questo serializza i thread di
    Waitress sul singolo `pyodbc.Connection` cached. Per il Piano 2 e'
    sufficiente (load basso). Piano 3 introdurra' una connessione per
    richiesta via `flask.g` per migliorare il throughput.
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None) -> None:
        self._cm = config_manager or ConfigManager()
        self._conn = DatabaseConnection(self._cm)
        self._lock = threading.Lock()

    def connect(self):
        return self._conn.connect()

    def disconnect(self) -> None:
        self._conn.disconnect()

    def cursor(self):
        """Ritorna un cursore. Caller responsabile della chiusura.

        Lock serializza l'accesso al `pyodbc.Connection` underlying.
        """
        with self._lock:
            return self.connect().cursor()
