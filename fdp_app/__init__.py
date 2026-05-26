"""Application factory."""
from __future__ import annotations

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from flask import Flask, render_template

from config.settings import Settings
from fdp_app.db import Database
from fdp_app.extensions import csrf, babel


def create_app(*, settings: type[Settings] | None = None,
               db: Database | None = None) -> Flask:
    """Costruisce l'app Flask. Le dipendenze possono essere iniettate per test."""
    settings = settings or Settings
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(settings)
    app.config["_settings_cls"] = settings

    # DI del database
    app.config["_db"] = db or Database()

    from fdp_app.pathtracks.routing import RoutingClient
    app.config["_routing"] = RoutingClient(
        osrm_base=settings.OSRM_BASE,
        ors_base=settings.ORS_BASE,
        ors_api_key=settings.ORS_API_KEY,
    )
    app.config["_workplace"] = settings.workplace()

    from fdp_app.pathtracks.bnr_client import BnrRateClient
    app.config["_bnr_client"] = BnrRateClient()

    csrf.init_app(app)

    def _select_locale():
        from flask import request
        cookie_lang = request.cookies.get(settings.LANGUAGE_COOKIE_NAME)
        if cookie_lang in settings.LANGUAGES:
            return cookie_lang
        browser_lang = request.accept_languages.best_match(settings.LANGUAGES)
        if browser_lang:
            return browser_lang
        return settings.BABEL_DEFAULT_LOCALE

    babel.init_app(app, locale_selector=_select_locale)

    @app.template_filter("eur_with_ron")
    def eur_with_ron(amount_eur, bnr_rate=None):
        """Return formatted '<EUR> (RON <ron> - tasso <rate>)' string.
        Falls back to EUR-only if bnr_rate is None."""
        from markupsafe import Markup
        if amount_eur is None:
            return ""
        eur_str = f"&euro; {amount_eur:.2f}"
        if bnr_rate is None or bnr_rate == 0:
            return Markup(eur_str)
        ron = float(amount_eur) * float(bnr_rate)
        ron_str = (
            f"<small class=\"text-muted ms-2\">"
            f"(RON {ron:.2f} &middot; "
            f"tasso {bnr_rate:.4f})"
            f"</small>"
        )
        return Markup(eur_str + " " + ron_str)

    _warn_if_missing_secret_key(app)
    _configure_logging(app)
    _register_error_handlers(app)
    _register_blueprints(app)

    from fdp_app.db import teardown_request_db
    app.teardown_appcontext(teardown_request_db)

    @app.route("/lang/<code>", methods=["POST"])
    def set_language(code):
        from flask import redirect, request, make_response
        app.logger.info(
            "LANG-SWITCH hit: code=%r form-next=%r referrer=%r "
            "has-csrf=%s current-cookie=%r remote=%s",
            code,
            request.form.get("next"),
            request.referrer,
            "csrf_token" in request.form,
            request.cookies.get(settings.LANGUAGE_COOKIE_NAME),
            request.remote_addr,
        )
        if code not in settings.LANGUAGES:
            app.logger.warning("LANG-SWITCH rejected: invalid code=%r", code)
            return ("Invalid language", 400)
        next_url = request.form.get("next") or request.referrer or "/"
        resp = make_response(redirect(next_url))
        resp.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            code,
            max_age=settings.LANGUAGE_COOKIE_MAX_AGE,
            samesite="Lax",
            httponly=False,
        )
        app.logger.info(
            "LANG-SWITCH ok: set %s=%s, redirect to %s",
            settings.LANGUAGE_COOKIE_NAME, code, next_url,
        )
        return resp

    # Fallback GET endpoint for clients where the POST-based selector fails
    # (Bootstrap dropdown interactions, blocking JS errors, locked-down
    # corporate browsers, etc). No CSRF needed because the only effect is
    # to set a cosmetic-language cookie — no data is modified.
    @app.route("/lang/set/<code>", methods=["GET"])
    @csrf.exempt
    def set_language_get(code):
        from flask import redirect, request, make_response
        app.logger.info(
            "LANG-SWITCH-GET hit: code=%r query-next=%r referrer=%r "
            "current-cookie=%r remote=%s",
            code,
            request.args.get("next"),
            request.referrer,
            request.cookies.get(settings.LANGUAGE_COOKIE_NAME),
            request.remote_addr,
        )
        if code not in settings.LANGUAGES:
            app.logger.warning("LANG-SWITCH-GET rejected: invalid code=%r", code)
            return ("Invalid language", 400)
        next_url = request.args.get("next") or request.referrer or "/"
        # Safety: only allow same-origin relative redirects to avoid open-redirect
        if not next_url.startswith("/") or next_url.startswith("//"):
            next_url = "/"
        resp = make_response(redirect(next_url))
        resp.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            code,
            max_age=settings.LANGUAGE_COOKIE_MAX_AGE,
            samesite="Lax",
            httponly=False,
        )
        app.logger.info(
            "LANG-SWITCH-GET ok: set %s=%s, redirect to %s",
            settings.LANGUAGE_COOKIE_NAME, code, next_url,
        )
        return resp

    return app


def _warn_if_missing_secret_key(app: Flask) -> None:
    """In produzione (TESTING=False) avverte se FDP_SECRET_KEY non e' settata."""
    if app.config.get("TESTING"):
        return
    if not os.environ.get("FDP_SECRET_KEY"):
        app.logger.warning(
            "FDP_SECRET_KEY env var non e' impostata. "
            "La SECRET_KEY corrente e' ephemeral: a ogni restart le sessioni "
            "esistenti saranno invalidate. Impostare FDP_SECRET_KEY in produzione."
        )


def _configure_logging(app: Flask) -> None:
    logs_dir = Path(__file__).resolve().parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    handler = TimedRotatingFileHandler(
        logs_dir / "app.log",
        when="midnight",
        backupCount=14,
        encoding="utf-8",
    )
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Unhandled exception", exc_info=e)
        return render_template("errors/500.html"), 500


def _register_blueprints(app: Flask) -> None:
    # Importazioni interne per evitare cicli
    from fdp_app.auth.routes import bp as auth_bp
    from fdp_app.dashboard.routes import bp as dashboard_bp
    from fdp_app.coordinates.routes import bp as coordinates_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(coordinates_bp)

    from fdp_app.pathtracks.routes import bp as pathtracks_bp
    app.register_blueprint(pathtracks_bp)

    from fdp_app.admin.routes import bp as admin_bp
    app.register_blueprint(admin_bp)
