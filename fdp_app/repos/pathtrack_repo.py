"""Repository per fdp.PathTracks (dichiarazione mensile con stato DRAFT/SUBMITTED)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional

from fdp_app.repos.base_repo import BaseRepo


_QUERY_FIND_FOR_MONTH = """
SELECT TOP 1
    PathTrackId, RegistryId, DatePathTrack, DeclaratedPathId, InBehalfOfId,
    ReimbursementType, NumberOfTrips, RoadKm, RateIdUsed, TaxiTotalEur,
    ComputedAmountEur, Status, SubmittedOn
FROM Employee.fdp.PathTracks
WHERE EmployeeHireHistoryId = ?
  AND DatePathTrack = ?
  AND DateOut IS NULL
"""

_QUERY_FIND_BY_ID = """
SELECT TOP 1
    PathTrackId, RegistryId, DatePathTrack, DeclaratedPathId, InBehalfOfId,
    ReimbursementType, NumberOfTrips, RoadKm, RateIdUsed, TaxiTotalEur,
    ComputedAmountEur, Status, SubmittedOn
FROM Employee.fdp.PathTracks
WHERE PathTrackId = ?
  AND EmployeeHireHistoryId = ?
  AND DateOut IS NULL
"""

_QUERY_FIND_BY_ID_IN_SUB_CDC = """
SELECT TOP 1
    pt.PathTrackId, pt.RegistryId, pt.DatePathTrack, pt.DeclaratedPathId,
    pt.InBehalfOfId, pt.ReimbursementType, pt.NumberOfTrips, pt.RoadKm,
    pt.RateIdUsed, pt.TaxiTotalEur, pt.ComputedAmountEur, pt.Status, pt.SubmittedOn
FROM Employee.fdp.PathTracks pt
JOIN Employee.dbo.EmployeeHireHistory h
     ON h.EmployeeHireHistoryId = COALESCE(pt.InBehalfOfId, pt.EmployeeHireHistoryId)
JOIN Employee.dbo.EmployeeCdcStories s
     ON s.EmployeeHireHistoryId = h.EmployeeHireHistoryId
    AND s.DateOut IS NULL
WHERE pt.PathTrackId = ?
  AND s.SubCdcId = ?
  AND pt.DateOut IS NULL
"""

_QUERY_INSERT = """
INSERT INTO Employee.fdp.PathTracks
    (EmployeeHireHistoryId, RegistryId, DatePathTrack, DeclaratedPathId,
     InBehalfOfId, ReimbursementType, NumberOfTrips, RoadKm, RateIdUsed,
     TaxiTotalEur, ComputedAmountEur, Status, SubmittedOn,
     DateOut, ReceivedOn, DateSys)
OUTPUT INSERTED.PathTrackId
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL,
        NULL, NULL, GETDATE())
"""

_QUERY_UPDATE_DRAFT = """
UPDATE Employee.fdp.PathTracks
SET ReimbursementType = ?,
    NumberOfTrips     = ?,
    RoadKm            = ?,
    RateIdUsed        = ?,
    TaxiTotalEur      = ?,
    ComputedAmountEur = ?
WHERE PathTrackId = ?
  AND EmployeeHireHistoryId = ?
  AND Status = 'DRAFT'
  AND DateOut IS NULL
"""

_QUERY_MARK_SUBMITTED = """
UPDATE Employee.fdp.PathTracks
SET Status      = 'SUBMITTED',
    SubmittedOn = GETDATE(),
    RegistryId  = ?
WHERE PathTrackId = ?
  AND EmployeeHireHistoryId = ?
  AND Status = 'DRAFT'
  AND DateOut IS NULL
"""

_QUERY_SOFT_DELETE = """
UPDATE Employee.fdp.PathTracks
SET DateOut = GETDATE()
WHERE PathTrackId = ?
  AND EmployeeHireHistoryId = ?
  AND Status = 'DRAFT'
  AND DateOut IS NULL
"""

_QUERY_LIST = """
SELECT
    PathTrackId, RegistryId, DatePathTrack, DeclaratedPathId, InBehalfOfId,
    ReimbursementType, NumberOfTrips, RoadKm, RateIdUsed, TaxiTotalEur,
    ComputedAmountEur, Status, SubmittedOn
FROM Employee.fdp.PathTracks
WHERE EmployeeHireHistoryId = ?
  AND DateOut IS NULL
ORDER BY DatePathTrack DESC
"""

_QUERY_LIST_SUB_CDC = """
SELECT
    pt.PathTrackId, pt.RegistryId, pt.DatePathTrack, pt.DeclaratedPathId,
    pt.InBehalfOfId, pt.ReimbursementType, pt.NumberOfTrips, pt.RoadKm,
    pt.RateIdUsed, pt.TaxiTotalEur, pt.ComputedAmountEur, pt.Status, pt.SubmittedOn,
    e.EmployeeSurname, e.EmployeeName
FROM Employee.fdp.PathTracks pt
JOIN Employee.dbo.EmployeeHireHistory h
     ON h.EmployeeHireHistoryId = COALESCE(pt.InBehalfOfId, pt.EmployeeHireHistoryId)
JOIN Employee.dbo.Employees e ON e.EmployeeId = h.EmployeeId
JOIN Employee.dbo.EmployeeCdcStories s
     ON s.EmployeeHireHistoryId = h.EmployeeHireHistoryId
    AND s.DateOut IS NULL
WHERE s.SubCdcId = ?
  AND pt.DateOut IS NULL
  /*FILTERS*/
ORDER BY pt.DatePathTrack DESC, e.EmployeeSurname, e.EmployeeName
"""


@dataclass(frozen=True)
class PathTrackRow:
    path_track_id: int
    registry_id: Optional[int]
    date_path_track: date
    declarated_path_id: int
    in_behalf_of_id: Optional[int]
    reimbursement_type: str
    number_of_trips: int
    road_km: float
    rate_id_used: Optional[int]
    taxi_total_eur: Optional[float]
    computed_amount_eur: float
    status: str
    submitted_on: Optional[datetime]


@dataclass(frozen=True)
class PathTrackWithEmployee:
    """A PathTrackRow enriched with the beneficiary employee's name."""
    row: "PathTrackRow"
    employee_surname: str
    employee_name: str

    @property
    def employee_full_name(self) -> str:
        return f"{self.employee_surname} {self.employee_name}"


def _row_to_obj(row) -> PathTrackRow:
    return PathTrackRow(
        path_track_id=row[0],
        registry_id=row[1] if row[1] is not None else None,
        date_path_track=row[2],
        declarated_path_id=row[3],
        in_behalf_of_id=row[4],
        reimbursement_type=row[5].rstrip() if isinstance(row[5], str) else row[5],
        number_of_trips=row[6],
        road_km=float(row[7]),
        rate_id_used=row[8],
        taxi_total_eur=float(row[9]) if row[9] is not None else None,
        computed_amount_eur=float(row[10]),
        status=row[11].rstrip() if isinstance(row[11], str) else row[11],
        submitted_on=row[12],
    )


class PathTrackRepo(BaseRepo):
    def find_active_for_month(self, *, employee_hire_history_id, date_path_track):
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_FIND_FOR_MONTH, employee_hire_history_id, date_path_track)
            row = cursor.fetchone()
        finally:
            cursor.close()
        return _row_to_obj(row) if row else None

    def find_by_id(self, *, path_track_id, employee_hire_history_id):
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_FIND_BY_ID, path_track_id, employee_hire_history_id)
            row = cursor.fetchone()
        finally:
            cursor.close()
        return _row_to_obj(row) if row else None

    def find_by_id_in_sub_cdc(self, *, path_track_id: int, sub_cdc_id: int):
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_FIND_BY_ID_IN_SUB_CDC, path_track_id, sub_cdc_id)
            row = cursor.fetchone()
        finally:
            cursor.close()
        return _row_to_obj(row) if row else None

    def insert(self, *, employee_hire_history_id, registry_id, date_path_track,
               declarated_path_id, in_behalf_of_id, reimbursement_type,
               number_of_trips, road_km, rate_id_used, taxi_total_eur,
               computed_amount_eur, status="DRAFT", submitted_on=None):
        cursor = self._open_cursor()
        try:
            cursor.execute(
                _QUERY_INSERT,
                employee_hire_history_id, registry_id, date_path_track,
                declarated_path_id, in_behalf_of_id, reimbursement_type,
                number_of_trips, road_km, rate_id_used,
                taxi_total_eur, computed_amount_eur, status, submitted_on,
            )
            row = cursor.fetchone()
            return int(row[0])
        finally:
            cursor.close()

    def update_draft(self, *, path_track_id, employee_hire_history_id,
                     reimbursement_type, number_of_trips, road_km,
                     rate_id_used, taxi_total_eur, computed_amount_eur):
        cursor = self._open_cursor()
        try:
            cursor.execute(
                _QUERY_UPDATE_DRAFT,
                reimbursement_type, number_of_trips, road_km,
                rate_id_used, taxi_total_eur, computed_amount_eur,
                path_track_id, employee_hire_history_id,
            )
            return cursor.rowcount > 0
        finally:
            cursor.close()

    def mark_as_submitted(self, *, path_track_id, employee_hire_history_id, registry_id):
        cursor = self._open_cursor()
        try:
            cursor.execute(
                _QUERY_MARK_SUBMITTED,
                registry_id, path_track_id, employee_hire_history_id,
            )
            return cursor.rowcount > 0
        finally:
            cursor.close()

    def soft_delete(self, *, path_track_id, employee_hire_history_id):
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_SOFT_DELETE, path_track_id, employee_hire_history_id)
            return cursor.rowcount > 0
        finally:
            cursor.close()

    def list_for_employee(self, *, employee_hire_history_id):
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_LIST, employee_hire_history_id)
            rows = cursor.fetchall()
        finally:
            cursor.close()
        return [_row_to_obj(r) for r in rows]

    def list_for_sub_cdc(
        self,
        *,
        sub_cdc_id: int,
        year: int | None = None,
        month: int | None = None,
        reimbursement_type: str | None = None,
    ) -> list:
        """Lists all path tracks for a SubCdcId, optionally filtered by year/month/type.

        The JOIN follows COALESCE(InBehalfOfId, EmployeeHireHistoryId) so that
        delegated entries are attributed to the represented employee.
        """
        filters = []
        params = [sub_cdc_id]
        if year is not None:
            filters.append("YEAR(pt.DatePathTrack) = ?")
            params.append(year)
        if month is not None:
            filters.append("MONTH(pt.DatePathTrack) = ?")
            params.append(month)
        if reimbursement_type:
            filters.append("pt.ReimbursementType = ?")
            params.append(reimbursement_type)
        sql = _QUERY_LIST_SUB_CDC.replace(
            "/*FILTERS*/",
            ("AND " + " AND ".join(filters)) if filters else "",
        )
        cursor = self._open_cursor()
        try:
            cursor.execute(sql, *params)
            rows = cursor.fetchall()
        finally:
            cursor.close()
        result = []
        for r in rows:
            ptrow = PathTrackRow(
                path_track_id=r[0],
                registry_id=r[1] if r[1] is not None else None,
                date_path_track=r[2],
                declarated_path_id=r[3],
                in_behalf_of_id=r[4],
                reimbursement_type=r[5].rstrip() if isinstance(r[5], str) else r[5],
                number_of_trips=r[6],
                road_km=float(r[7]),
                rate_id_used=r[8],
                taxi_total_eur=float(r[9]) if r[9] is not None else None,
                computed_amount_eur=float(r[10]),
                status=r[11].rstrip() if isinstance(r[11], str) else r[11],
                submitted_on=r[12],
            )
            result.append(PathTrackWithEmployee(
                row=ptrow,
                employee_surname=r[13],
                employee_name=r[14],
            ))
        return result
