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
