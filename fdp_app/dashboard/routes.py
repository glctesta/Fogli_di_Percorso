"""Dashboard utente."""
from __future__ import annotations

from flask import Blueprint, redirect, render_template, session, url_for

from fdp_app.auth.decorators import login_required

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def root():
    return redirect(url_for("dashboard.index"))


@bp.route("/dashboard")
@login_required
def index():
    return render_template(
        "dashboard/index.html",
        full_name=session.get("full_name"),
        sub_cdc_id=session.get("sub_cdc_id"),
        function_code=session.get("function_code"),
    )
