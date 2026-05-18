"""Test del repository RegistryRepo (chiamata SP)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from fdp_app.repos.registry_repo import RegistryRepo


def _make_db(fetchone=None):
    db = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    db.cursor.return_value = cursor
    return db, cursor


def test_generate_new_registry_id_returns_int():
    db, cursor = _make_db(fetchone=(12345,))
    repo = RegistryRepo(db)

    result = repo.generate(issued_by_full_name="Rossi Mario")

    assert result == 12345
    cursor.close.assert_called_once()


def test_generate_calls_sp_with_correct_parameters():
    db, cursor = _make_db(fetchone=(1,))
    repo = RegistryRepo(db)

    repo.generate(issued_by_full_name="Bianchi Luigi")

    sql_text, *params = cursor.execute.call_args[0]
    assert "Employee.dbo.Registro" in sql_text
    assert "@RegistryTypeId" in sql_text
    assert "@anno" in sql_text
    assert "@DataDocumento" in sql_text
    assert "@IussedBy" in sql_text
    assert "@EmployeerId" in sql_text
    assert params[0] == 790
    assert params[-1] == 2
    assert "Bianchi Luigi" in params


def test_generate_raises_if_sp_returns_no_row():
    db, cursor = _make_db(fetchone=None)
    repo = RegistryRepo(db)

    with pytest.raises(RuntimeError, match="non ha restituito"):
        repo.generate(issued_by_full_name="x")


def test_generate_closes_cursor_on_exception():
    db, cursor = _make_db()
    cursor.execute.side_effect = RuntimeError("DB down")
    repo = RegistryRepo(db)

    with pytest.raises(RuntimeError):
        repo.generate(issued_by_full_name="x")
    cursor.close.assert_called_once()
