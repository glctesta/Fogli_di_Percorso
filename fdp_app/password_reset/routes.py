"""Route per il reset password via email.

Endpoint:
  GET/POST /password/forgot        -> richiesta link di reset
  GET/POST /password/reset/<token> -> impostazione nuova password

Principi:
  - No user enumeration: /forgot risponde sempre con lo stesso messaggio.
  - Token a uso singolo, con scadenza, salvato come hash.
  - Rate limiting sulla richiesta (riusa lo stesso limiter del login).
"""
from __future__ import annotations

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request,
    url_for,
)
from flask_babel import _

from fdp_app.auth.rate_limit import LoginRateLimiter
from fdp_app.repos.employee_repo import EmployeeRepo
from fdp_app.repos.password_reset_repo import PasswordResetTokenRepo
from fdp_app.password_reset.service import PasswordResetService

bp = Blueprint("password_reset", __name__, url_prefix="/password")

# Messaggio neutro mostrato sempre dopo /forgot (anti-enumeration).
_NEUTRAL_MSG = (
    "Se l'utente esiste, riceverai a breve un'email con le istruzioni "
    "per reimpostare la password."
)

# Rate limiter dedicato per le richieste di reset (per-processo, come login).
_reset_limiter: LoginRateLimiter | None = None


def _get_reset_limiter() -> LoginRateLimiter:
    global _reset_limiter
    if _reset_limiter is None:
        s = current_app.config["_settings_cls"]
        _reset_limiter = LoginRateLimiter(
            max_attempts=s.LOGIN_MAX_ATTEMPTS,
            window_seconds=s.LOGIN_WINDOW_SECONDS,
        )
    return _reset_limiter


def _build_service() -> PasswordResetService:
    db = current_app.config["_db"]
    return PasswordResetService(
        employee_repo=EmployeeRepo(db),
        token_repo=PasswordResetTokenRepo(db),
    )


def _send_reset_email(email, token_plain: str) -> None:
    """Invia il link di reset. Errori loggati ma non propagati all'utente
    (per non rivelare l'esito ne' bloccare la risposta neutra)."""
    s = current_app.config["_settings_cls"]
    reset_url = s.APP_URL.rstrip("/") + url_for(
        "password_reset.reset", token=token_plain
    )
    subject = _("Reimpostazione password - Fogli di Percorso")
    body = _(
        "Buongiorno %(name)s,\n\n"
        "Abbiamo ricevuto una richiesta di reimpostazione della password "
        "per il tuo account.\n\n"
        "Per impostare una nuova password clicca sul link seguente "
        "(valido 30 minuti):\n"
        "  %(url)s\n\n"
        "Se non hai richiesto tu questa operazione, ignora questa email: "
        "la tua password attuale resta valida.\n\n"
        "Cordialmente,\nSistema Fogli di Percorso",
        name=email.full_name, url=reset_url,
    )
    try:
        from email_connector import EmailSender
        EmailSender().send_email(email.work_email, subject, body, is_html=False)
        current_app.logger.info("Password reset email sent (recipient hidden)")
    except Exception as e:  # noqa: BLE001 - non deve mai propagarsi all'utente
        current_app.logger.error("Password reset email FAILED: %s", e)


@bp.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "GET":
        return render_template("password_reset/forgot.html")

    nome_user = (request.form.get("nome_user") or "").strip()

    rl = _get_reset_limiter()
    # Rate-limit per username per evitare flood di email/token.
    if nome_user and not rl.is_blocked(nome_user):
        rl.register_failure(nome_user)  # conta come "tentativo"
        service = _build_service()
        req = service.request_reset(nome_user, request_ip=request.remote_addr)
        if req is not None:
            _send_reset_email(req.email, req.token_plain)
            current_app.logger.info(
                "Password reset requested for user=%s", nome_user
            )

    # Risposta SEMPRE identica, a prescindere dall'esito.
    flash(_(_NEUTRAL_MSG), "info")
    return render_template("password_reset/forgot.html"), 200


@bp.route("/reset/<token>", methods=["GET", "POST"])
def reset(token: str):
    service = _build_service()
    nome_user = service.validate_token(token)

    if nome_user is None:
        flash(_("Il link non e' valido o e' scaduto. Richiedine uno nuovo."),
              "danger")
        return redirect(url_for("password_reset.forgot"))

    if request.method == "GET":
        return render_template("password_reset/reset.html", token=token)

    pw1 = request.form.get("password") or ""
    pw2 = request.form.get("password_confirm") or ""

    err = service.validate_new_password(pw1, pw2)
    if err is not None:
        flash(_(err), "danger")
        return render_template("password_reset/reset.html", token=token), 200

    # Transazione esplicita: mark_used + update_password devono essere atomici.
    # La connection per-request ha autocommit=True di default, quindi la
    # disabilitiamo per la durata dell'operazione.
    from fdp_app.db import get_request_db
    conn = get_request_db()
    prev_autocommit = conn.autocommit
    conn.autocommit = False
    try:
        ok = service.consume_token_and_set_password(token, pw1)
        if ok:
            conn.commit()
        else:
            conn.rollback()
    except Exception:
        conn.rollback()
        current_app.logger.exception("Password reset transaction failed")
        ok = False
    finally:
        conn.autocommit = prev_autocommit

    if not ok:
        flash(_("Impossibile reimpostare la password. "
                "Il link potrebbe essere scaduto: richiedine uno nuovo."),
              "danger")
        return redirect(url_for("password_reset.forgot"))

    current_app.logger.info("Password reset completed for user=%s", nome_user)
    flash(_("Password reimpostata con successo. Ora puoi accedere."),
          "success")
    return redirect(url_for("auth.login"))
