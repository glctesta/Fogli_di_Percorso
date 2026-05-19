"""Test del decoratore login_required."""
from __future__ import annotations

from flask import Flask, Blueprint

from fdp_app.auth.decorators import login_required


def _build_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"

    # Stub auth blueprint with a /login endpoint so url_for('auth.login') resolves
    auth_bp = Blueprint("auth", __name__)

    @auth_bp.route("/login")
    def login():
        return "login"

    app.register_blueprint(auth_bp)

    @app.route("/secret")
    @login_required
    def secret():
        return "ok"

    return app


def test_login_required_redirects_when_anonymous():
    app = _build_app()
    client = app.test_client()
    response = client.get("/secret", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_login_required_allows_when_session_has_user_id():
    app = _build_app()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = 123
    response = client.get("/secret")
    assert response.status_code == 200
    assert response.data == b"ok"


# ---- admin_required ----

from fdp_app.auth.decorators import admin_required


def _build_app_with_admin_route():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"

    # Stub auth blueprint with /login
    auth_bp = Blueprint("auth", __name__)

    @auth_bp.route("/login")
    def login():
        return "login"

    app.register_blueprint(auth_bp)

    @app.route("/admin-only")
    @admin_required
    def admin_only():
        return "ok"

    @app.errorhandler(403)
    def forbidden(_e):
        return "forbidden", 403

    return app


def test_admin_required_redirects_when_anonymous():
    app = _build_app_with_admin_route()
    client = app.test_client()
    response = client.get("/admin-only", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_admin_required_403_when_fc_below_or_equal_60():
    app = _build_app_with_admin_route()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["function_code"] = 60
    response = client.get("/admin-only")
    assert response.status_code == 403


def test_admin_required_allows_when_fc_above_60():
    app = _build_app_with_admin_route()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["function_code"] = 70
    response = client.get("/admin-only")
    assert response.status_code == 200
    assert response.data == b"ok"


def test_admin_required_403_when_function_code_missing():
    app = _build_app_with_admin_route()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        # no function_code set
    response = client.get("/admin-only")
    assert response.status_code == 403
