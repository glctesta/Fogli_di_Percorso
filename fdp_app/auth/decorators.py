"""Decoratori di autorizzazione."""
from __future__ import annotations

from functools import wraps
from typing import Callable

from flask import redirect, session, url_for


def login_required(view: Callable) -> Callable:
    """Reindirizza a /login se non c'e' utente in sessione."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapper
