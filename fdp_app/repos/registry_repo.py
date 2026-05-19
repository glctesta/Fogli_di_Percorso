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

from fdp_app.repos.base_repo import BaseRepo


_SP_CALL = """
EXEC Employee.dbo.Registro
    @RegistryTypeId = ?,
    @anno = YEAR(GETDATE()),
    @DataDocumento = GETDATE(),
    @IussedBy = ?,
    @EmployeerId = ?
"""


class RegistryRepo(BaseRepo):
    REGISTRY_TYPE_ID = 790
    EMPLOYER_ID = 2

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
