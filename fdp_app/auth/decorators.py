"""Decoratori di autorizzazione."""
from __future__ import annotations

from functools import wraps
from typing import Callable

from flask import current_app, redirect, session, url_for

from fdp_app.auth.permissions import can_access_reimbursement_reporting


def login_required(view: Callable) -> Callable:
    """Reindirizza a /login se non c'e' utente in sessione."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapper


def admin_required(view: Callable) -> Callable:
    """Verifica che l'utente abbia FunctionCode > 60.

    Anonymous -> redirect /login. FC <= 60 o assente -> 403.
    """

    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        fc = session.get("function_code")
        if fc is None or fc <= 60:
            from flask import abort
            abort(403)
        return view(*args, **kwargs)

    return wrapper


def reimbursement_reporting_required(view: Callable) -> Callable:
    """Consente accesso solo agli utenti abilitati alla sezione rimborsi."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        user_id = session.get("user_id")
        function_code = session.get("function_code")
        allowed = can_access_reimbursement_reporting(
            user_id=session.get("user_id"),
            function_code=session.get("function_code"),
            settings_cls=current_app.config["_settings_cls"],
            db=current_app.config.get("_db"),
        )
        current_app.logger.info(
            "REIMBURSEMENT-ACCESS user_id=%s function_code=%s allowed=%s env_user_ids=%s env_function_codes=%s",
            user_id,
            function_code,
            allowed,
            current_app.config["_settings_cls"].REIMBURSEMENT_REPORT_ALLOWED_USER_IDS,
            current_app.config["_settings_cls"].REIMBURSEMENT_REPORT_ALLOWED_FUNCTION_CODES,
        )
        if not allowed:
            from flask import abort
            abort(403)
        return view(*args, **kwargs)

    return wrapper
