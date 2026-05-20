"""Test del repository PathTrackDocRepo."""
from __future__ import annotations

from unittest.mock import MagicMock

from fdp_app.repos.doc_repo import PathTrackDocRepo, PathTrackDocRow


def _make_db(fetchone=None, fetchall=None):
    db = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    cursor.fetchall.return_value = fetchall or []
    db.cursor.return_value = cursor
    return db, cursor


def test_insert_returns_new_doc_id():
    db, cursor = _make_db(fetchone=(42,))
    repo = PathTrackDocRepo(db)

    doc_id = repo.insert(
        path_track_id=100,
        doc_title="Foglio di Percorso - Aprile 2026",
        pdf_bytes=b"%PDF-1.4\n...some content...",
    )

    assert doc_id == 42
    sql_text, *params = cursor.execute.call_args[0]
    assert "INSERT INTO Employee.fdp.PathTrackDocs" in sql_text
    assert "DocumentOfTrackPath" in sql_text
    assert b"%PDF-" in params[0]
    assert "Foglio di Percorso - Aprile 2026" in params


def test_list_for_pathtrack_returns_rows():
    db, cursor = _make_db(fetchall=[
        (1, "Foglio percorso", 100),
        (2, "Ricevuta 1", 100),
    ])
    repo = PathTrackDocRepo(db)

    rows = repo.list_for_pathtrack(path_track_id=100)

    assert len(rows) == 2
    assert rows[0].doc_id == 1
    assert rows[0].doc_title == "Foglio percorso"
    assert rows[1].doc_title == "Ricevuta 1"


def test_soft_delete_for_pathtrack_marks_all_docs():
    db, cursor = _make_db()
    cursor.rowcount = 3
    repo = PathTrackDocRepo(db)

    count = repo.soft_delete_all_for_pathtrack(path_track_id=100)

    assert count == 3
    sql_text, *params = cursor.execute.call_args[0]
    assert "UPDATE Employee.fdp.PathTrackDocs" in sql_text
    assert "SET DateOut = GETDATE()" in sql_text
    assert "PathTrackId = ?" in sql_text
    assert params == [100]


def test_get_blob_returns_pdf_bytes():
    db, cursor = _make_db(fetchone=(b"%PDF-1.4\n...", "Title"))
    repo = PathTrackDocRepo(db)

    pdf_bytes, title = repo.get_blob(doc_id=42)

    assert pdf_bytes.startswith(b"%PDF-")
    assert title == "Title"


def test_find_owner_employee_for_doc_returns_owner_when_self():
    db, cursor = _make_db(fetchone=(10, 10))
    repo = PathTrackDocRepo(db)
    result = repo.find_owner_employee_for_doc(doc_id=42)
    assert result == (10, 10)
    cursor.close.assert_called_once()


def test_find_owner_employee_for_doc_returns_beneficiary_when_in_behalf():
    db, _ = _make_db(fetchone=(10, 25))  # 10 inserisce per conto di 25
    repo = PathTrackDocRepo(db)
    result = repo.find_owner_employee_for_doc(doc_id=42)
    assert result == (10, 25)


def test_find_owner_employee_for_doc_returns_none_when_missing():
    db, _ = _make_db(fetchone=None)
    repo = PathTrackDocRepo(db)
    assert repo.find_owner_employee_for_doc(doc_id=999) is None


def test_find_owner_employee_for_doc_uses_join():
    db, cursor = _make_db(fetchone=None)
    repo = PathTrackDocRepo(db)
    repo.find_owner_employee_for_doc(doc_id=99)
    sql_text, *_params = cursor.execute.call_args[0]
    assert "JOIN Employee.fdp.PathTracks" in sql_text
    assert "COALESCE(pt.InBehalfOfId, pt.EmployeeHireHistoryId)" in sql_text


def test_find_sub_cdc_for_doc_returns_sub_cdc_id():
    db, _ = _make_db(fetchone=(42,))
    repo = PathTrackDocRepo(db)
    assert repo.find_sub_cdc_for_doc(doc_id=99) == 42


def test_find_sub_cdc_for_doc_returns_none_when_missing():
    db, _ = _make_db(fetchone=None)
    repo = PathTrackDocRepo(db)
    assert repo.find_sub_cdc_for_doc(doc_id=999) is None
