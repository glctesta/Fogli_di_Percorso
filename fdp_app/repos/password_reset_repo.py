"""Repository per fdp.PasswordResetTokens.

Memorizza solo l'hash SHA-256 del token. Il token in chiaro non viene mai
persistito: vive unicamente nel link inviato via email.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fdp_app.repos.base_repo import BaseRepo


_QUERY_INSERT = """
INSERT INTO Employee.fdp.PasswordResetTokens
    (NomeUser, TokenHash, ExpiresAt, RequestIp)
OUTPUT INSERTED.TokenId
VALUES (?, ?, ?, ?)
"""

_QUERY_FIND_BY_HASH = """
SELECT TOP 1 TokenId, NomeUser, ExpiresAt, UsedAt
FROM Employee.fdp.PasswordResetTokens
WHERE TokenHash = ?
"""

_QUERY_MARK_USED = """
UPDATE Employee.fdp.PasswordResetTokens
SET UsedAt = GETDATE()
WHERE TokenId = ?
  AND UsedAt IS NULL
"""

# Invalida tutti i token ancora aperti di un utente (es. nuova richiesta o
# dopo un reset riuscito).
_QUERY_INVALIDATE_OPEN = """
UPDATE Employee.fdp.PasswordResetTokens
SET UsedAt = GETDATE()
WHERE NomeUser = ?
  AND UsedAt IS NULL
"""


@dataclass(frozen=True)
class ResetToken:
    token_id: int
    nome_user: str
    expires_at: datetime
    used_at: Optional[datetime]

    def is_consumable(self, now: datetime) -> bool:
        """Token valido: mai usato e non scaduto."""
        return self.used_at is None and self.expires_at > now


class PasswordResetTokenRepo(BaseRepo):
    def insert(self, *, nome_user: str, token_hash: str,
               expires_at: datetime, request_ip: Optional[str]) -> int:
        cursor = self._open_cursor()
        try:
            cursor.execute(
                _QUERY_INSERT, (nome_user, token_hash, expires_at, request_ip)
            )
            row = cursor.fetchone()
            return int(row[0])
        finally:
            cursor.close()

    def find_by_hash(self, token_hash: str) -> Optional[ResetToken]:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_FIND_BY_HASH, (token_hash,))
            row = cursor.fetchone()
        finally:
            cursor.close()
        if row is None:
            return None
        return ResetToken(
            token_id=int(row[0]),
            nome_user=row[1],
            expires_at=row[2],
            used_at=row[3],
        )

    def mark_used(self, token_id: int) -> int:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_MARK_USED, (token_id,))
            return cursor.rowcount
        finally:
            cursor.close()

    def invalidate_open_for_user(self, nome_user: str) -> int:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_INVALIDATE_OPEN, (nome_user,))
            return cursor.rowcount
        finally:
            cursor.close()
