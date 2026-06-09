"""Repository per whitelist accesso sezione report rimborsi."""
from __future__ import annotations

from dataclasses import dataclass

from fdp_app.repos.base_repo import BaseRepo


_QUERY_IS_ALLOWED = """
SELECT TOP 1 1
FROM Employee.fdp.ReimbursementReportingPermissions
WHERE DateOut IS NULL
  AND (
        (PermissionType = 'USER' AND TargetValue = ?)
        OR
        (PermissionType = 'FUNCTION_CODE' AND TargetValue = ?)
      )
"""

_QUERY_LIST = """
SELECT PermissionId, PermissionType, TargetValue, Notes, UserSys, DateSys
FROM Employee.fdp.ReimbursementReportingPermissions
WHERE DateOut IS NULL
ORDER BY PermissionType, TargetValue
"""

_QUERY_INSERT = """
INSERT INTO Employee.fdp.ReimbursementReportingPermissions
    (PermissionType, TargetValue, Notes, UserSys, DateOut, DateSys)
VALUES (?, ?, ?, ?, NULL, GETDATE())
"""

_QUERY_SOFT_DELETE = """
UPDATE Employee.fdp.ReimbursementReportingPermissions
SET DateOut = GETDATE()
WHERE PermissionId = ?
  AND DateOut IS NULL
"""


@dataclass(frozen=True)
class ReimbursementPermission:
    permission_id: int
    permission_type: str
    target_value: int
    notes: str
    user_sys: str
    date_sys: object


class ReimbursementPermissionRepo(BaseRepo):
    def is_allowed(self, *, user_id: int, function_code: int | None) -> bool:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_IS_ALLOWED, user_id, function_code or -1)
            return cursor.fetchone() is not None
        finally:
            cursor.close()

    def list_active(self) -> list[ReimbursementPermission]:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_LIST)
            rows = cursor.fetchall()
        finally:
            cursor.close()
        return [
            ReimbursementPermission(
                permission_id=r[0],
                permission_type=r[1],
                target_value=r[2],
                notes=r[3] or "",
                user_sys=r[4] or "",
                date_sys=r[5],
            )
            for r in rows
        ]

    def add(self, *, permission_type: str, target_value: int, notes: str, user_sys: str) -> None:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_INSERT, permission_type, target_value, notes, user_sys)
        finally:
            cursor.close()

    def soft_delete(self, *, permission_id: int) -> int:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_SOFT_DELETE, permission_id)
            return cursor.rowcount
        finally:
            cursor.close()
