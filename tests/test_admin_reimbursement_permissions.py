"""Test route admin whitelist report rimborsi."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _login_admin(client, eh_id=10, sub_cdc_id=42, fc=70):
    with client.session_transaction() as sess:
        sess["user_id"] = eh_id
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = sub_cdc_id
        sess["function_code"] = fc


@pytest.fixture
def mock_permission_repo():
    with patch("fdp_app.admin.routes.ReimbursementPermissionRepo") as cls:
        instance = MagicMock()
        instance.list_active.return_value = []
        instance.soft_delete.return_value = 1
        cls.return_value = instance
        yield instance


def test_permissions_page_requires_admin(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["function_code"] = 50
    response = client.get("/admin/reimbursement-permissions")
    assert response.status_code == 403


def test_permissions_page_renders(client, mock_permission_repo):
    _login_admin(client)
    response = client.get("/admin/reimbursement-permissions")
    assert response.status_code == 200


def test_permissions_add_calls_repo(client, mock_permission_repo):
    _login_admin(client)
    response = client.post(
        "/admin/reimbursement-permissions",
        data={
            "permission_type": "USER",
            "target_value": "123",
            "notes": "Test",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    kwargs = mock_permission_repo.add.call_args.kwargs
    assert kwargs["permission_type"] == "USER"
    assert kwargs["target_value"] == 123


def test_permissions_delete_calls_repo(client, mock_permission_repo):
    _login_admin(client)
    response = client.post(
        "/admin/reimbursement-permissions/9/delete",
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 302
    mock_permission_repo.soft_delete.assert_called_once_with(permission_id=9)
