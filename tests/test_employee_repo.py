"""Test del repository EmployeeRepo (mock pyodbc cursor)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from fdp_app.repos.employee_repo import EmployeeRepo, EmployeeAuthRow


def _make_db_with_rows(rows):
    """Costruisce un mock Database che ritorna `rows` da fetchone/fetchall."""
    db = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = rows[0] if rows else None
    cursor.fetchall.return_value = rows
    db.cursor.return_value = cursor
    return db


def test_find_user_by_nomeuser_returns_row_when_found():
    row = ("plain_pwd", 1234, "Rossi", "Mario", 77, 65)
    db = _make_db_with_rows([row])
    repo = EmployeeRepo(db)

    result = repo.find_user_by_nomeuser("mrossi")

    assert isinstance(result, EmployeeAuthRow)
    assert result.password == "plain_pwd"
    assert result.employee_hire_history_id == 1234
    assert result.surname == "Rossi"
    assert result.name == "Mario"
    assert result.sub_cdc_id == 77
    assert result.function_code == 65


def test_find_user_by_nomeuser_returns_none_when_missing():
    db = _make_db_with_rows([])
    repo = EmployeeRepo(db)

    result = repo.find_user_by_nomeuser("ghost")

    assert result is None


def test_find_user_by_nomeuser_passes_username_as_parameter():
    db = _make_db_with_rows([])
    repo = EmployeeRepo(db)

    repo.find_user_by_nomeuser("xyz")

    cursor = db.cursor.return_value
    # Si verifica che execute sia stato chiamato con la query e un solo parametro = "xyz"
    args, _kwargs = cursor.execute.call_args
    sql_text, *params = args
    assert "k.NomeUser = ?" in sql_text
    assert params == ["xyz"]
