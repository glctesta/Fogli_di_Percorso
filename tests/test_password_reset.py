"""Test del flusso di reset password.

Esegue con: pytest tests/test_password_reset.py
Non richiede SQL Server: pyodbc e' stubbato e il DB e' un fake in-memory.
"""
from __future__ import annotations

import re
import sys
import types
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# Stub pyodbc prima di importare il package (db_connection lo importa a top-level).
sys.modules.setdefault("pyodbc", types.ModuleType("pyodbc"))

from fdp_app.password_reset.service import PasswordResetService  # noqa: E402
from fdp_app.repos.employee_repo import UserEmail  # noqa: E402
from fdp_app.repos.password_reset_repo import ResetToken  # noqa: E402


# --------------------------------------------------------------------------- #
# Unit test: service
# --------------------------------------------------------------------------- #
@pytest.fixture
def svc():
    return PasswordResetService(MagicMock(), MagicMock())


@pytest.mark.parametrize("pw1,pw2,expected_ok", [
    ("abcd1234", "abcd1234", True),
    ("abc", "abc", False),            # troppo corta
    ("abcdefgh", "abcdefgh", False),  # senza numeri
    ("12345678", "12345678", False),  # senza lettere
    ("abcd1234", "different1", False),  # non coincidono
    ("", "", False),
])
def test_password_validation(svc, pw1, pw2, expected_ok):
    assert (svc.validate_new_password(pw1, pw2) is None) is expected_ok


def test_request_reset_unknown_user_no_token(svc):
    svc._employees.find_email_by_nomeuser.return_value = None
    assert svc.request_reset("ghost") is None
    svc._tokens.insert.assert_not_called()


def test_request_reset_stores_hash_not_plaintext(svc):
    svc._employees.find_email_by_nomeuser.return_value = UserEmail(
        "a@b.it", "Rossi", "Mario")
    req = svc.request_reset("mrossi", request_ip="1.2.3.4")
    assert req.email.work_email == "a@b.it"
    kwargs = svc._tokens.insert.call_args.kwargs
    assert kwargs["token_hash"] == svc._hash_token(req.token_plain)
    assert kwargs["token_hash"] != req.token_plain
    assert len(kwargs["token_hash"]) == 64
    svc._tokens.invalidate_open_for_user.assert_called_once_with("mrossi")


def test_validate_token_states(svc):
    now = datetime(2026, 6, 9, 12, 0, 0)
    cases = {
        "valid": (ResetToken(1, "u", now + timedelta(minutes=5), None), "u"),
        "expired": (ResetToken(2, "u", now - timedelta(minutes=1), None), None),
        "used": (ResetToken(3, "u", now + timedelta(minutes=5),
                            now - timedelta(minutes=1)), None),
        "missing": (None, None),
    }
    for _name, (rec, expected) in cases.items():
        svc._tokens.find_by_hash.return_value = rec
        assert svc.validate_token("t", now=now) == expected


def test_consume_single_use(svc):
    now = datetime(2026, 6, 9, 12, 0, 0)
    svc._tokens.find_by_hash.return_value = ResetToken(
        1, "u", now + timedelta(minutes=5), None)
    svc._tokens.mark_used.return_value = 1
    svc._employees.update_password.return_value = 1
    assert svc.consume_token_and_set_password("t", "abcd1234", now=now) is True

    # mark_used race -> rowcount 0 -> no password change
    svc._employees.update_password.reset_mock()
    svc._tokens.mark_used.return_value = 0
    assert svc.consume_token_and_set_password("t", "abcd1234", now=now) is False
    svc._employees.update_password.assert_not_called()


# --------------------------------------------------------------------------- #
# Integration test: HTTP
# --------------------------------------------------------------------------- #
class _FakeCursor:
    def __init__(self, store):
        self.store = store
        self._row = None
        self.rowcount = 0

    def execute(self, q, params=()):
        ql = " ".join(q.split())
        if "FROM resetservices.dbo.tbuserkey" in ql and "WorkEmail" in ql:
            self._row = (("user@corp.it", "Rossi", "Mario")
                         if params[0] == "mrossi" else None)
        elif "INSERT INTO Employee.fdp.PasswordResetTokens" in ql:
            self.store["hash"] = params[1]
            self._row = (42,)
        elif "FROM Employee.fdp.PasswordResetTokens" in ql and "SELECT" in ql:
            h = params[0]
            if h == self.store.get("hash") and not self.store.get("used"):
                self._row = (42, "mrossi",
                             datetime.now() + timedelta(minutes=10), None)
            else:
                self._row = None
        elif ("UPDATE Employee.fdp.PasswordResetTokens" in ql
              and "TokenId" in ql):
            self.store["used"] = True
            self.rowcount = 1
        elif ("UPDATE Employee.fdp.PasswordResetTokens" in ql
              and "NomeUser" in ql):
            self.rowcount = 0
        elif "UPDATE resetservices.dbo.tbuserkey" in ql:
            self.store["new_pw"] = params[0]
            self.rowcount = 1

    def fetchone(self):
        return self._row

    def fetchall(self):
        return []

    def close(self):
        pass


class _FakeConn:
    def __init__(self, store):
        self.store = store
        self.autocommit = True

    def cursor(self):
        return _FakeCursor(self.store)

    def commit(self):
        self.store["committed"] = True

    def rollback(self):
        self.store["rolled_back"] = True

    def close(self):
        pass


@pytest.fixture
def client():
    from fdp_app import create_app
    from fdp_app.db import Database
    from config.settings import Settings

    store = {}
    db = Database()
    db.connect = lambda: _FakeConn(store)
    Settings.WTF_CSRF_ENABLED = False
    app = create_app(settings=Settings, db=db)
    app.config["TESTING"] = True
    return app.test_client(), store


def test_http_full_flow(client):
    c, store = client
    sent = {}

    def fake_send(self, to, subj, body, is_html=False):
        sent["to"] = to
        sent["body"] = body

    with patch("email_connector.EmailSender.send_email", fake_send):
        # unknown user -> neutral, no email
        c.post("/password/forgot", data={"nome_user": "ghost"})
        assert "to" not in sent

        # known user -> email with link
        c.post("/password/forgot", data={"nome_user": "mrossi"})
        assert sent["to"] == "user@corp.it"
        token = re.search(r"/password/reset/([A-Za-z0-9_-]+)",
                          sent["body"]).group(1)

        # mismatch rejected
        c.post(f"/password/reset/{token}",
               data={"password": "abcd1234", "password_confirm": "x"})
        assert "new_pw" not in store

        # valid reset
        r = c.post(f"/password/reset/{token}",
                   data={"password": "abcd1234", "password_confirm": "abcd1234"})
        assert r.status_code == 302 and "/login" in r.headers["Location"]
        assert store["new_pw"] == "abcd1234"

        # single use enforced
        r = c.post(f"/password/reset/{token}",
                   data={"password": "zzzz9999", "password_confirm": "zzzz9999"})
        assert r.status_code == 302  # back to /forgot
