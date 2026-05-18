"""Wrapper attorno a db_connection.DatabaseConnection per dependency injection."""
from __future__ import annotations

from typing import Optional

from config_manager import ConfigManager
from db_connection import DatabaseConnection


class Database:
    """Wrapper iniettabile: in produzione delega a DatabaseConnection esistente.

    In test viene sostituito con MagicMock.
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None) -> None:
        self._cm = config_manager or ConfigManager()
        self._conn = DatabaseConnection(self._cm)

    def connect(self):
        return self._conn.connect()

    def disconnect(self) -> None:
        self._conn.disconnect()

    def cursor(self):
        """Ritorna un cursore. Caller responsabile della chiusura."""
        return self.connect().cursor()
