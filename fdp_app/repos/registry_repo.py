"""Repository per la chiamata a Employee.dbo.Registro SP.

La SP assegna un nuovo RegistryId per `RegistryTypeId=790` (Fogli di Percorso).
Parametri:
    @RegistryTypeId = 790
    @anno = YEAR(GETDATE())
    @DataDocumento = GETDATE()
    @IussedBy = <cognome nome dell'utente loggato>
    @EmployeerId = 2

La SP restituisce il nuovo RegistryId come risultato (SELECT finale).
"""
from __future__ import annotations

from flask import has_app_context


_SP_CALL = """
EXEC Employee.dbo.Registro
    @RegistryTypeId = ?,
    @anno = YEAR(GETDATE()),
    @DataDocumento = GETDATE(),
    @IussedBy = ?,
    @EmployeerId = ?
"""


class RegistryRepo:
    REGISTRY_TYPE_ID = 790
    EMPLOYER_ID = 2

    def __init__(self, db) -> None:
        self._db = db

    def _open_cursor(self):
        if has_app_context():
            from fdp_app.db import get_request_db
            return get_request_db().cursor()
        return self._db.cursor()

    def generate(self, *, issued_by_full_name: str) -> int:
        cursor = self._open_cursor()
        try:
            cursor.execute(
                _SP_CALL,
                self.REGISTRY_TYPE_ID,
                issued_by_full_name,
                self.EMPLOYER_ID,
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError(
                    "Employee.dbo.Registro non ha restituito alcun RegistryId"
                )
            return int(row[0])
        finally:
            cursor.close()
