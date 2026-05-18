"""Test end-to-end delle route di autenticazione (con mock del repo)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fdp_app.repos.employee_repo import EmployeeAuthRow


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    import fdp_app.auth.routes as routes
    routes._rate_limiter = None
    yield
    routes._rate_limiter = None


@pytest.fixture
def mock_repo():
    with patch("fdp_app.auth.routes.EmployeeRepo") as repo_cls:
        instance = MagicMock()
        repo_cls.return_value = instance
        yield instance


def test_get_login_page_renders(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"<form" in response.data.lower()
    assert b"nome_user" in response.data.lower()


def test_post_login_success_with_fc_gt_60(client, mock_repo):
    mock_repo.find_user_by_nomeuser.return_value = EmployeeAuthRow(
        password="pw", employee_hire_history_id=10,
        surname="Rossi", name="Mario", sub_cdc_id=5, function_code=70,
    )
    response = client.post(
        "/login",
        data={"nome_user": "mrossi", "password": "pw"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]
    with client.session_transaction() as sess:
        assert sess["user_id"] == 10
        assert sess["full_name"] == "Rossi Mario"
        assert sess["sub_cdc_id"] == 5
        assert sess["function_code"] == 70


def test_post_login_rejects_fc_below_60(client, mock_repo):
    mock_repo.find_user_by_nomeuser.return_value = EmployeeAuthRow(
        password="pw", employee_hire_history_id=10,
        surname="Rossi", name="Mario", sub_cdc_id=5, function_code=40,
    )
    response = client.post(
        "/login",
        data={"nome_user": "mrossi", "password": "pw"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"credenziali" in response.data.lower()
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_post_login_rejects_wrong_password(client, mock_repo):
    mock_repo.find_user_by_nomeuser.return_value = EmployeeAuthRow(
        password="real", employee_hire_history_id=10,
        surname="Rossi", name="Mario", sub_cdc_id=5, function_code=70,
    )
    response = client.post(
        "/login",
        data={"nome_user": "mrossi", "password": "WRONG"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"credenziali" in response.data.lower()


def test_post_login_rejects_unknown_user(client, mock_repo):
    mock_repo.find_user_by_nomeuser.return_value = None
    response = client.post(
        "/login",
        data={"nome_user": "ghost", "password": "x"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"credenziali" in response.data.lower()


def test_logout_via_get_is_405_method_not_allowed(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 99
    response = client.get("/logout")
    assert response.status_code == 405


def test_logout_via_post_clears_session_and_redirects(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 99
        sess["full_name"] = "Test User"
    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_rate_limit_blocks_after_5_failures(client, mock_repo):
    mock_repo.find_user_by_nomeuser.return_value = None  # always fail
    for _ in range(5):
        client.post("/login", data={"nome_user": "spammer", "password": "x"})

    response = client.post(
        "/login",
        data={"nome_user": "spammer", "password": "x"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"troppi tentativi" in response.data.lower()
