"""Repository per fdp.BnrRates (tassi EUR->RON)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from fdp_app.repos.base_repo import BaseRepo


_QUERY_FIND_STANDARD_FOR_DATE = """
SELECT TOP 1 RateId, RateValueRonPerEur, Source, ValidFrom, ValidTo
FROM Employee.fdp.BnrRates
WHERE IsStandard = 1
  AND ValidFrom <= ?
  AND (ValidTo IS NULL OR ValidTo >= ?)
ORDER BY ValidFrom DESC
"""

_QUERY_FIND_LATEST_FOR_DATE = """
SELECT TOP 1 RateId, RateValueRonPerEur, Source, ValidFrom, ValidTo
FROM Employee.fdp.BnrRates
WHERE ValidFrom <= ?
ORDER BY ValidFrom DESC, RateId DESC
"""

_QUERY_INSERT = """
INSERT INTO Employee.fdp.BnrRates
    (RateValueRonPerEur, Source, ValidFrom, ValidTo, IsStandard, UserSys)
OUTPUT INSERTED.RateId
VALUES (?, ?, ?, ?, ?, ?)
"""

_QUERY_LIST_STANDARDS = """
SELECT RateId, RateValueRonPerEur, Source, ValidFrom, ValidTo, IsStandard, UserSys
FROM Employee.fdp.BnrRates
WHERE IsStandard = 1
ORDER BY ValidFrom DESC
"""

_QUERY_LIST_RECENT = """
SELECT TOP (?) RateId, RateValueRonPerEur, Source, ValidFrom, ValidTo, IsStandard, UserSys
FROM Employee.fdp.BnrRates
ORDER BY ValidFrom DESC, RateId DESC
"""


@dataclass(frozen=True)
class BnrRate:
    rate_id: int
    rate_value_ron_per_eur: float
    source: str
    valid_from: date
    valid_to: Optional[date]
    is_standard: bool = False
    user_sys: str = ""


def _row_to_obj(row) -> BnrRate:
    return BnrRate(
        rate_id=int(row[0]),
        rate_value_ron_per_eur=float(row[1]),
        source=row[2].rstrip() if isinstance(row[2], str) else row[2],
        valid_from=row[3],
        valid_to=row[4],
        is_standard=bool(row[5]) if len(row) > 5 else False,
        user_sys=row[6] if len(row) > 6 and row[6] is not None else "",
    )


class BnrRateRepo(BaseRepo):
    def find_standard_for(self, target_date: date) -> Optional[BnrRate]:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_FIND_STANDARD_FOR_DATE, target_date, target_date)
            row = cursor.fetchone()
        finally:
            cursor.close()
        if row is None:
            return None
        return BnrRate(
            rate_id=int(row[0]),
            rate_value_ron_per_eur=float(row[1]),
            source=row[2].rstrip() if isinstance(row[2], str) else row[2],
            valid_from=row[3],
            valid_to=row[4],
        )

    def find_latest_cached_for(self, target_date: date) -> Optional[BnrRate]:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_FIND_LATEST_FOR_DATE, target_date)
            row = cursor.fetchone()
        finally:
            cursor.close()
        if row is None:
            return None
        return BnrRate(
            rate_id=int(row[0]),
            rate_value_ron_per_eur=float(row[1]),
            source=row[2].rstrip() if isinstance(row[2], str) else row[2],
            valid_from=row[3],
            valid_to=row[4],
        )

    def insert(self, *, rate_value_ron_per_eur: float, source: str,
               valid_from: date, valid_to: Optional[date] = None,
               is_standard: bool = False, user_sys: str = "system") -> int:
        cursor = self._open_cursor()
        try:
            cursor.execute(
                _QUERY_INSERT,
                rate_value_ron_per_eur, source, valid_from, valid_to,
                1 if is_standard else 0, user_sys,
            )
            row = cursor.fetchone()
            return int(row[0])
        finally:
            cursor.close()

    def list_standards(self) -> List[BnrRate]:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_LIST_STANDARDS)
            rows = cursor.fetchall()
        finally:
            cursor.close()
        return [_row_to_obj(r) for r in rows]

    def list_recent(self, *, limit: int = 20) -> List[BnrRate]:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_LIST_RECENT, limit)
            rows = cursor.fetchall()
        finally:
            cursor.close()
        return [_row_to_obj(r) for r in rows]
