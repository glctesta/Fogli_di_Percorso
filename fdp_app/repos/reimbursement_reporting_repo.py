"""Repository per report rimborsi casa-ufficio con integrazioni manuali."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fdp_app.repos.base_repo import BaseRepo


_QUERY_EMPLOYEE_MONTH_SUMMARY = """
SELECT
    h.EmployeeHireHistoryId,
    e.EmployeeSurname,
    e.EmployeeName,
    COALESCE(SUM(pt.ComputedAmountEur), 0) AS DeclaredAmountEur,
    COALESCE(MAX(adj.AdditionalAmountEur), 0) AS AdditionalAmountEur,
    COALESCE(MAX(adj.DeductionAmountEur), 0) AS DeductionAmountEur,
    MAX(adj.Notes) AS Notes,
    MAX(adj.DateSys) AS LastUpdatedOn
FROM Employee.dbo.EmployeeHireHistory h
JOIN Employee.dbo.Employees e
     ON e.EmployeeId = h.EmployeeId
JOIN Employee.dbo.EmployeeCdcStories s
     ON s.EmployeeHireHistoryId = h.EmployeeHireHistoryId
    AND s.DateOut IS NULL
LEFT JOIN Employee.fdp.PathTracks pt
       ON COALESCE(pt.InBehalfOfId, pt.EmployeeHireHistoryId) = h.EmployeeHireHistoryId
      AND pt.DateOut IS NULL
      AND YEAR(pt.DatePathTrack) = ?
      AND MONTH(pt.DatePathTrack) = ?
LEFT JOIN Employee.fdp.PathTrackAdditionalReimbursements adj
       ON adj.EmployeeHireHistoryId = h.EmployeeHireHistoryId
      AND adj.SubCdcId = s.SubCdcId
      AND adj.YearRef = ?
      AND adj.MonthRef = ?
      AND adj.DateOut IS NULL
WHERE h.EndWorkDate IS NULL
  AND h.EmployeerId = 2
  AND s.SubCdcId = ?
GROUP BY h.EmployeeHireHistoryId, e.EmployeeSurname, e.EmployeeName
ORDER BY e.EmployeeSurname, e.EmployeeName
"""

_QUERY_EXISTING_ADJUSTMENT = """
SELECT TOP 1 AdjustmentId
FROM Employee.fdp.PathTrackAdditionalReimbursements
WHERE EmployeeHireHistoryId = ?
  AND SubCdcId = ?
  AND YearRef = ?
  AND MonthRef = ?
  AND DateOut IS NULL
"""

_QUERY_INSERT_ADJUSTMENT = """
INSERT INTO Employee.fdp.PathTrackAdditionalReimbursements
    (EmployeeHireHistoryId, SubCdcId, YearRef, MonthRef, AdditionalAmountEur,
     DeductionAmountEur, Notes, UserSys, DateOut, DateSys)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, GETDATE())
"""

_QUERY_UPDATE_ADJUSTMENT = """
UPDATE Employee.fdp.PathTrackAdditionalReimbursements
SET AdditionalAmountEur = ?,
    DeductionAmountEur  = ?,
    Notes               = ?,
    UserSys             = ?,
    DateSys             = GETDATE()
WHERE AdjustmentId = ?
"""


@dataclass(frozen=True)
class ReimbursementReportRow:
    employee_hire_history_id: int
    employee_surname: str
    employee_name: str
    declared_amount_eur: float
    additional_amount_eur: float
    deduction_amount_eur: float
    notes: str
    last_updated_on: datetime | None

    @property
    def employee_full_name(self) -> str:
        return f"{self.employee_surname} {self.employee_name}"


class ReimbursementReportingRepo(BaseRepo):
    def list_month_summary(
        self,
        *,
        sub_cdc_id: int,
        year: int,
        month: int,
    ) -> list[ReimbursementReportRow]:
        cursor = self._open_cursor()
        try:
            cursor.execute(
                _QUERY_EMPLOYEE_MONTH_SUMMARY,
                year,
                month,
                year,
                month,
                sub_cdc_id,
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()
        return [
            ReimbursementReportRow(
                employee_hire_history_id=r[0],
                employee_surname=r[1],
                employee_name=r[2],
                declared_amount_eur=float(r[3] or 0),
                additional_amount_eur=float(r[4] or 0),
                deduction_amount_eur=float(r[5] or 0),
                notes=r[6] or "",
                last_updated_on=r[7],
            )
            for r in rows
        ]

    def upsert_adjustment(
        self,
        *,
        employee_hire_history_id: int,
        sub_cdc_id: int,
        year: int,
        month: int,
        additional_amount_eur: float,
        deduction_amount_eur: float,
        notes: str,
        user_sys: str,
    ) -> None:
        cursor = self._open_cursor()
        try:
            cursor.execute(
                _QUERY_EXISTING_ADJUSTMENT,
                employee_hire_history_id,
                sub_cdc_id,
                year,
                month,
            )
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    _QUERY_UPDATE_ADJUSTMENT,
                    additional_amount_eur,
                    deduction_amount_eur,
                    notes,
                    user_sys,
                    existing[0],
                )
            else:
                cursor.execute(
                    _QUERY_INSERT_ADJUSTMENT,
                    employee_hire_history_id,
                    sub_cdc_id,
                    year,
                    month,
                    additional_amount_eur,
                    deduction_amount_eur,
                    notes,
                    user_sys,
                )
        finally:
            cursor.close()
