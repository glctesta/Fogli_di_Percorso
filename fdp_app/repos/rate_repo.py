"""Repository per fdp.PathTrackReimbursementRates."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from fdp_app.repos.base_repo import BaseRepo


_QUERY = """
SELECT TOP 1 RateId, AvgConsumptionKmL, AvgFuelPriceEurL
FROM Employee.fdp.PathTrackReimbursementRates
WHERE ValidFrom <= ?
  AND (ValidTo IS NULL OR ValidTo >= ?)
ORDER BY ValidFrom DESC
"""

_QUERY_INSERT = """
INSERT INTO Employee.fdp.PathTrackReimbursementRates
    (AvgConsumptionKmL, AvgFuelPriceEurL, ValidFrom, ValidTo, UserSys)
OUTPUT INSERTED.RateId
VALUES (?, ?, ?, ?, ?)
"""

_QUERY_LIST_RECENT = """
SELECT TOP (?) RateId, AvgConsumptionKmL, AvgFuelPriceEurL,
       ValidFrom, ValidTo, UserSys
FROM Employee.fdp.PathTrackReimbursementRates
ORDER BY ValidFrom DESC, RateId DESC
"""


@dataclass(frozen=True)
class Rate:
    rate_id: int
    avg_consumption_km_l: float
    avg_fuel_price_eur_l: float
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    user_sys: str = ""


class RateRepo(BaseRepo):
    def find_for_date(self, target_date: date) -> Optional[Rate]:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY, target_date, target_date)
            row = cursor.fetchone()
        finally:
            cursor.close()
        if row is None:
            return None
        return Rate(
            rate_id=int(row[0]),
            avg_consumption_km_l=float(row[1]),
            avg_fuel_price_eur_l=float(row[2]),
        )

    def insert(self, *, avg_consumption_km_l: float, avg_fuel_price_eur_l: float,
               valid_from: date, valid_to: Optional[date], user_sys: str) -> int:
        cursor = self._open_cursor()
        try:
            cursor.execute(
                _QUERY_INSERT,
                avg_consumption_km_l, avg_fuel_price_eur_l,
                valid_from, valid_to, user_sys,
            )
            row = cursor.fetchone()
            return int(row[0])
        finally:
            cursor.close()

    def list_recent(self, *, limit: int = 20) -> List[Rate]:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_LIST_RECENT, limit)
            rows = cursor.fetchall()
        finally:
            cursor.close()
        return [
            Rate(
                rate_id=int(r[0]),
                avg_consumption_km_l=float(r[1]),
                avg_fuel_price_eur_l=float(r[2]),
                valid_from=r[3],
                valid_to=r[4],
                user_sys=r[5] if r[5] is not None else "",
            )
            for r in rows
        ]
