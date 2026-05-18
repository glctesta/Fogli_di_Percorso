"""Route di autenticazione."""
from __future__ import annotations

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request,
    session, url_for,
)

from fdp_app.auth.rate_limit import LoginRateLimiter
from fdp_app.auth.service import AuthService
from fdp_app.repos.employee_repo import EmployeeRepo

bp = Blueprint("auth", __name__)

# Singleton rate limiter (per processo). Inizializzato lazy.
_rate_limiter: LoginRateLimiter | None = None


def _get_rate_limiter() -> LoginRateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        s = current_app.config["_settings_cls"]
        _rate_limiter = LoginRateLimiter(
            max_attempts=s.LOGIN_MAX_ATTEMPTS,
            window_seconds=s.LOGIN_WINDOW_SECONDS,
        )
    return _rate_limiter


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("auth/login.html")

    nome_user = (request.form.get("nome_user") or "").strip()
    password = request.form.get("password") or ""

    rl = _get_rate_limiter()
    if rl.is_blocked(nome_user):
        flash("Troppi tentativi falliti, riprovare piu' tardi.", "danger")
        return render_template("auth/login.html"), 200

    db = current_app.config["_db"]
    repo = EmployeeRepo(db)
    s = current_app.config["_settings_cls"]
    service = AuthService(repo, min_function_code=s.MIN_FUNCTION_CODE_FOR_LOGIN)

    ctx = service.authenticate(nome_user, password)
    if ctx is None:
        rl.register_failure(nome_user)
        flash("Credenziali non valide.", "danger")
        current_app.logger.info("Login failed for %s", nome_user)
        return render_template("auth/login.html"), 200

    rl.register_success(nome_user)
    session.clear()
    session["user_id"] = ctx.employee_hire_history_id
    session["full_name"] = ctx.full_name
    session["sub_cdc_id"] = ctx.sub_cdc_id
    session["function_code"] = ctx.function_code
    session.permanent = True
    current_app.logger.info("Login OK for user_id=%s", ctx.employee_hire_history_id)
    return redirect(url_for("dashboard.index"))


@bp.route("/logout", methods=["POST"])
def logout():
    user_id = session.get("user_id")
    session.clear()
    current_app.logger.info("Logout user_id=%s", user_id)
    return redirect(url_for("auth.login"))
