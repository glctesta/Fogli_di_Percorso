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

_QUERY_EMAIL_BY_NOMEUSER = """
SELECT TOP 1 ea.WorkEmail,
       e.EmployeeSurname,
       e.EmployeeName
FROM resetservices.dbo.tbuserkey k
JOIN Employee.dbo.Employees e
     ON e.EmployeeId = k.idanga
JOIN Employee.dbo.EmployeeAddress ea
     ON ea.EmployeeId = e.EmployeeId
    AND ea.DateOut IS NULL
    AND ea.WorkEmail IS NOT NULL
WHERE k.NomeUser = ?
"""

_QUERY_UPDATE_PASSWORD = """
UPDATE resetservices.dbo.tbuserkey
SET pass = ?
WHERE NomeUser = ?
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

_QUERY_PENDING_FOR_MONTH = """
SELECT DISTINCT
    h.EmployeeHireHistoryId,
    e.EmployeeSurname,
    e.EmployeeName,
    ea.WorkEmail
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
    AND f.FunctionCode > ?
JOIN Employee.dbo.EmployeeAddress ea
     ON ea.EmployeeId = e.EmployeeId
    AND ea.DateOut IS NULL
    AND ea.WorkEmail IS NOT NULL
WHERE NOT EXISTS (
    SELECT 1 FROM Employee.fdp.PathTracks pt
    WHERE pt.DatePathTrack = ?
      AND pt.Status = 'SUBMITTED'
      AND pt.DateOut IS NULL
      AND (pt.EmployeeHireHistoryId = h.EmployeeHireHistoryId
           OR pt.InBehalfOfId = h.EmployeeHireHistoryId)
)
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
class UserEmail:
    """Indirizzo email + nominativo, per l'invio del link di reset."""
    work_email: str
    surname: str
    name: str

    @property
    def full_name(self) -> str:
        return f"{self.surname} {self.name}"


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


@dataclass(frozen=True)
class PendingEmployee:
    employee_hire_history_id: int
    surname: str
    name: str
    work_email: str

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

    def find_pending_for_month(
        self, *, date_path_track, min_function_code: int = 60,
    ) -> list:
        """Lista dipendenti FC>min_function_code che non hanno ancora inviato
        una dichiarazione per il mese date_path_track (ne' in proprio
        ne' come InBehalfOfId).
        """
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_PENDING_FOR_MONTH,
                            min_function_code, date_path_track)
            rows = cursor.fetchall()
        finally:
            cursor.close()
        return [
            PendingEmployee(
                employee_hire_history_id=r[0],
                surname=r[1],
                name=r[2],
                work_email=r[3],
            )
            for r in rows
        ]

    def find_email_by_nomeuser(self, nome_user: str) -> Optional["UserEmail"]:
        """Ritorna (work_email, surname, name) per lo username, o None se
        l'utente non esiste o non ha una WorkEmail attiva."""
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_EMAIL_BY_NOMEUSER, (nome_user,))
            row = cursor.fetchone()
        finally:
            cursor.close()
        if row is None or not row[0]:
            return None
        return UserEmail(work_email=row[0], surname=row[1], name=row[2])

    def update_password(self, nome_user: str, new_password: str) -> int:
        """Aggiorna la password (colonna `pass`) per lo username.

        Ritorna il numero di righe aggiornate (0 = utente inesistente).
        NB: il valore viene scritto nel formato attualmente in uso dalla
        tabella condivisa `resetservices.dbo.tbuserkey`. Vedi nota di
        sicurezza nel service.
        """
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_UPDATE_PASSWORD, (new_password, nome_user))
            return cursor.rowcount
        finally:
            cursor.close()

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
