"""Repository per fdp.PathTrackCoordinates (gestione punto di partenza)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


_QUERY_FIND_ACTIVE = """
SELECT TOP 1
    PathTrackCoordinateId,
    PathTrackName,
    Coordinates.Lat AS lat,
    Coordinates.Long AS lon,
    RoadKmToWorkplace
FROM Employee.fdp.PathTrackCoordinates
WHERE EmployeerHireHistoryId = ?
  AND DateOut IS NULL
ORDER BY DateSys DESC
"""

_QUERY_INSERT = """
INSERT INTO Employee.fdp.PathTrackCoordinates
    (EmployeerHireHistoryId, PathTrackName, Coordinates, RoadKmToWorkplace,
     DateOut, DateSys)
OUTPUT INSERTED.PathTrackCoordinateId
VALUES
    (?, ?, geography::Point(?, ?, 4326), ?, NULL, GETDATE())
"""

_QUERY_SOFT_DELETE = """
UPDATE Employee.fdp.PathTrackCoordinates
SET DateOut = GETDATE()
WHERE PathTrackCoordinateId = ?
  AND EmployeerHireHistoryId = ?
  AND DateOut IS NULL
"""


@dataclass(frozen=True)
class ActiveCoordinate:
    coordinate_id: int
    label: str
    lat: float
    lon: float
    road_km_to_workplace: Optional[float]


class CoordinateRepo:
    def __init__(self, db) -> None:
        self._db = db

    def _open_cursor(self):
        from flask import has_app_context
        if has_app_context():
            from fdp_app.db import get_request_db
            return get_request_db().cursor()
        return self._db.cursor()

    def find_active(self, employee_hire_history_id: int) -> Optional[ActiveCoordinate]:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_FIND_ACTIVE, employee_hire_history_id)
            row = cursor.fetchone()
        finally:
            cursor.close()
        if row is None:
            return None
        return ActiveCoordinate(
            coordinate_id=row[0],
            label=row[1],
            lat=float(row[2]),
            lon=float(row[3]),
            road_km_to_workplace=float(row[4]) if row[4] is not None else None,
        )

    def insert(
        self,
        *,
        employee_hire_history_id: int,
        label: str,
        lat: float,
        lon: float,
        road_km_to_workplace: float,
    ) -> int:
        cursor = self._open_cursor()
        try:
            cursor.execute(
                _QUERY_INSERT,
                employee_hire_history_id,
                label,
                lat,
                lon,
                road_km_to_workplace,
            )
            row = cursor.fetchone()
            return int(row[0])
        finally:
            cursor.close()

    def soft_delete(
        self, *, coordinate_id: int, employee_hire_history_id: int
    ) -> bool:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_SOFT_DELETE, coordinate_id, employee_hire_history_id)
            return cursor.rowcount > 0
        finally:
            cursor.close()
