"""Repository per fdp.PathTrackDocs (BLOB dei PDF caricati)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from flask import has_app_context


_QUERY_INSERT = """
INSERT INTO Employee.fdp.PathTrackDocs
    (DocumentOfTrackPath, DocTitle, PathTrackId, DateSys)
OUTPUT INSERTED.PathTrackDocId
VALUES (?, ?, ?, GETDATE())
"""

_QUERY_LIST = """
SELECT PathTrackDocId, DocTitle, PathTrackId
FROM Employee.fdp.PathTrackDocs
WHERE PathTrackId = ?
  AND DateOut IS NULL
ORDER BY PathTrackDocId
"""

_QUERY_SOFT_DELETE_ALL = """
UPDATE Employee.fdp.PathTrackDocs
SET DateOut = GETDATE()
WHERE PathTrackId = ?
  AND DateOut IS NULL
"""

_QUERY_GET_BLOB = """
SELECT TOP 1 DocumentOfTrackPath, DocTitle
FROM Employee.fdp.PathTrackDocs
WHERE PathTrackDocId = ?
  AND DateOut IS NULL
"""


@dataclass(frozen=True)
class PathTrackDocRow:
    doc_id: int
    doc_title: str
    path_track_id: int


class PathTrackDocRepo:
    def __init__(self, db) -> None:
        self._db = db

    def _open_cursor(self):
        if has_app_context():
            from fdp_app.db import get_request_db
            return get_request_db().cursor()
        return self._db.cursor()

    def insert(self, *, path_track_id: int, doc_title: str, pdf_bytes: bytes) -> int:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_INSERT, pdf_bytes, doc_title, path_track_id)
            row = cursor.fetchone()
            return int(row[0])
        finally:
            cursor.close()

    def list_for_pathtrack(self, *, path_track_id: int) -> List[PathTrackDocRow]:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_LIST, path_track_id)
            rows = cursor.fetchall()
        finally:
            cursor.close()
        return [PathTrackDocRow(doc_id=r[0], doc_title=r[1], path_track_id=r[2]) for r in rows]

    def soft_delete_all_for_pathtrack(self, *, path_track_id: int) -> int:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_SOFT_DELETE_ALL, path_track_id)
            return int(cursor.rowcount)
        finally:
            cursor.close()

    def get_blob(self, *, doc_id: int) -> Tuple[bytes, str]:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_GET_BLOB, doc_id)
            row = cursor.fetchone()
            if row is None:
                raise FileNotFoundError(f"Documento {doc_id} non trovato")
            return bytes(row[0]), str(row[1])
        finally:
            cursor.close()
