"""Repository per fdp.PathTrackReimbursementRates."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from flask import has_app_context


_QUERY = """
SELECT TOP 1 RateId, AvgConsumptionKmL, AvgFuelPriceEurL
FROM Employee.fdp.PathTrackReimbursementRates
WHERE ValidFrom <= ?
  AND (ValidTo IS NULL OR ValidTo >= ?)
ORDER BY ValidFrom DESC
"""


@dataclass(frozen=True)
class Rate:
    rate_id: int
    avg_consumption_km_l: float
    avg_fuel_price_eur_l: float


class RateRepo:
    def __init__(self, db) -> None:
        self._db = db

    def _open_cursor(self):
        if has_app_context():
            from fdp_app.db import get_request_db
            return get_request_db().cursor()
        return self._db.cursor()

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
