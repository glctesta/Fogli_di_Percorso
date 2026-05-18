"""Test del service di autenticazione."""
from __future__ import annotations

from unittest.mock import MagicMock

from fdp_app.auth.service import AuthService, UserContext
from fdp_app.repos.employee_repo import EmployeeAuthRow


def _row(function_code: int, password: str = "secret") -> EmployeeAuthRow:
    return EmployeeAuthRow(
        password=password,
        employee_hire_history_id=999,
        surname="Bianchi",
        name="Luigi",
        sub_cdc_id=42,
        function_code=function_code,
    )


def test_authenticate_returns_user_context_for_valid_user_with_fc_gt_60():
    repo = MagicMock()
    repo.find_user_by_nomeuser.return_value = _row(function_code=65)
    service = AuthService(repo, min_function_code=60)

    ctx = service.authenticate("lbianchi", "secret")

    assert isinstance(ctx, UserContext)
    assert ctx.employee_hire_history_id == 999
    assert ctx.full_name == "Bianchi Luigi"
    assert ctx.sub_cdc_id == 42
    assert ctx.function_code == 65


def test_authenticate_rejects_user_with_fc_equal_to_60():
    """Threshold esclusivo: FC == 60 NON e' ammesso."""
    repo = MagicMock()
    repo.find_user_by_nomeuser.return_value = _row(function_code=60)
    service = AuthService(repo, min_function_code=60)

    ctx = service.authenticate("user60", "secret")

    assert ctx is None


def test_authenticate_rejects_user_with_fc_below_60():
    repo = MagicMock()
    repo.find_user_by_nomeuser.return_value = _row(function_code=40)
    service = AuthService(repo, min_function_code=60)

    ctx = service.authenticate("user40", "secret")

    assert ctx is None


def test_authenticate_rejects_wrong_password():
    repo = MagicMock()
    repo.find_user_by_nomeuser.return_value = _row(function_code=65, password="real")
    service = AuthService(repo, min_function_code=60)

    ctx = service.authenticate("user", "wrong")

    assert ctx is None


def test_authenticate_returns_none_when_user_not_found():
    repo = MagicMock()
    repo.find_user_by_nomeuser.return_value = None
    service = AuthService(repo, min_function_code=60)

    ctx = service.authenticate("ghost", "any")

    assert ctx is None


def test_authenticate_does_not_call_repo_when_inputs_empty():
    repo = MagicMock()
    service = AuthService(repo, min_function_code=60)

    assert service.authenticate("", "secret") is None
    assert service.authenticate("user", "") is None
    repo.find_user_by_nomeuser.assert_not_called()
