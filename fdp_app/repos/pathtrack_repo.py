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
