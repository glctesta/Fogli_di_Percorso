"""Repository per i dati anagrafici degli employee."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


_QUERY_FIND_BY_NOMEUSER = """
SELECT k.pass,
       h.EmployeeHireHistoryId,
       e.EmployeeSurname,
       e.EmployeeName,
       s.SubCdcId,
       f.FunctionCode
FROM Employee.dbo.Employees e
JOIN resetservices.dbo.tbuserkey k
     ON e.EmployeeId = k.idanga
JOIN Employee.dbo.EmployeeHireHistory h
     ON h.EmployeeId = e.EmployeeId
    AND h.EndWorkDate IS NULL
    AND h.EmployeerId = 2
JOIN Employee.dbo.EmployeeCdcStories s
     ON s.EmployeeHireHistoryId = h.EmployeeHireHistoryId
    AND s.DateOut IS NULL
JOIN Employee.dbo.Functions f
     ON f.FunctionId = s.FunctionId
WHERE k.NomeUser = ?
"""


@dataclass(frozen=True)
class EmployeeAuthRow:
    """Risultato della query di login."""
    password: str
    employee_hire_history_id: int
    surname: str
    name: str
    sub_cdc_id: int
    function_code: int


class EmployeeRepo:
    """Accesso ai dati anagrafici."""

    def __init__(self, db) -> None:
        self._db = db

    def _open_cursor(self):
        """Apre un cursore. In production usa flask.g; in test delega a self._db.cursor()."""
        from flask import has_app_context
        if has_app_context():
            from fdp_app.db import get_request_db
            return get_request_db().cursor()
        return self._db.cursor()

    def find_user_by_nomeuser(self, nome_user: str) -> Optional[EmployeeAuthRow]:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_FIND_BY_NOMEUSER, nome_user)
            row = cursor.fetchone()
        finally:
            cursor.close()
        if row is None:
            return None
        return EmployeeAuthRow(
            password=row[0],
            employee_hire_history_id=row[1],
            surname=row[2],
            name=row[3],
            sub_cdc_id=row[4],
            function_code=row[5],
        )
