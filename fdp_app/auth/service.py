"""Logica di autenticazione applicativa."""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Optional

from fdp_app.repos.employee_repo import EmployeeRepo


@dataclass(frozen=True)
class UserContext:
    """Contenuto della session dopo login riuscito."""
    employee_hire_history_id: int
    full_name: str
    sub_cdc_id: int
    function_code: int


class AuthService:
    """Verifica credenziali e perimetro di accesso (FC > min_function_code)."""

    def __init__(self, repo: EmployeeRepo, min_function_code: int) -> None:
        self._repo = repo
        self._min_fc = min_function_code

    def authenticate(self, nome_user: str, password: str) -> Optional[UserContext]:
        if not nome_user or not password:
            return None

        row = self._repo.find_user_by_nomeuser(nome_user)
        if row is None:
            return None

        if not secrets.compare_digest(row.password, password):
            return None

        if row.function_code <= self._min_fc:
            return None

        return UserContext(
            employee_hire_history_id=row.employee_hire_history_id,
            full_name=f"{row.surname} {row.name}",
            sub_cdc_id=row.sub_cdc_id,
            function_code=row.function_code,
        )
