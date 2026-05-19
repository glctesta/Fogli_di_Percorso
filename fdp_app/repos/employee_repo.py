"""Repository per i dati anagrafici degli employee."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fdp_app.repos.base_repo import BaseRepo


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

_QUERY_REPRESENTABLE = """
SELECT
    h.EmployeeHireHistoryId,
    e.EmployeeSurname,
    e.EmployeeName,
    s.SubCdcId,
    f.FunctionCode
FROM Employee.dbo.Employees e
JOIN Employee.dbo.EmployeeHireHistory h
     ON h.EmployeeId = e.EmployeeId
    AND h.EndWorkDate IS NULL
    AND h.EmployeerId = 2
JOIN Employee.dbo.EmployeeCdcStories s
     ON s.EmployeeHireHistoryId = h.EmployeeHireHistoryId
    AND s.DateOut IS NULL
JOIN Employee.dbo.Functions f
     ON f.FunctionId = s.FunctionId
WHERE s.SubCdcId = ?
  AND f.FunctionCode < ?
ORDER BY e.EmployeeSurname, e.EmployeeName
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


@dataclass(frozen=True)
class RepresentableEmployee:
    employee_hire_history_id: int
    surname: str
    name: str
    sub_cdc_id: int
    function_code: int

    @property
    def full_name(self) -> str:
        return f"{self.surname} {self.name}"


class EmployeeRepo(BaseRepo):
    """Accesso ai dati anagrafici."""

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

    def find_representable_for(
        self, *, sub_cdc_id: int, min_function_code: int = 60,
    ) -> list:
        """Lists employees (in the same SubCdc) that the logged-in user
        (FC > min_function_code) can represent. They have FunctionCode < min."""
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_REPRESENTABLE, sub_cdc_id, min_function_code)
            rows = cursor.fetchall()
        finally:
            cursor.close()
        return [
            RepresentableEmployee(
                employee_hire_history_id=r[0],
                surname=r[1],
                name=r[2],
                sub_cdc_id=r[3],
                function_code=r[4],
            )
            for r in rows
        ]
