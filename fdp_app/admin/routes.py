"""Route amministrative (rappresentanza colleghi + storico + export)."""
from __future__ import annotations

from flask import (
    Blueprint, current_app, render_template, session,
)

from fdp_app.auth.decorators import admin_required, login_required
from fdp_app.repos.employee_repo import EmployeeRepo

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/representable", methods=["GET"])
@login_required
@admin_required
def representable():
    db = current_app.config["_db"]
    employee_repo = EmployeeRepo(db)
    employees = employee_repo.find_representable_for(
        sub_cdc_id=session["sub_cdc_id"],
        min_function_code=current_app.config["_settings_cls"].MIN_FUNCTION_CODE_FOR_LOGIN,
    )
    return render_template(
        "admin/representable.html",
        employees=employees,
    )


# Stub temporanei per Task 8/9 (history, export). Necessari perche'
# representable.html referenzia url_for('admin.history').
@bp.route("/history", methods=["GET"], endpoint="history")
@login_required
@admin_required
def _history_stub():
    return "history - not yet implemented", 501


@bp.route("/export", methods=["GET"], endpoint="export")
@login_required
@admin_required
def _export_stub():
    return "export - not yet implemented", 501
