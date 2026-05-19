"""Route amministrative (rappresentanza colleghi + storico + export)."""
from __future__ import annotations

from flask import (
    Blueprint, Response, abort, current_app, render_template, request, session,
)

from fdp_app.auth.decorators import admin_required, login_required
from fdp_app.repos.employee_repo import EmployeeRepo
from fdp_app.repos.pathtrack_repo import PathTrackRepo

bp = Blueprint("admin", __name__, url_prefix="/admin")

_MONTH_NAMES_IT = [
    "", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]


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


@bp.route("/history", methods=["GET"])
@login_required
@admin_required
def history():
    db = current_app.config["_db"]
    pathtrack_repo = PathTrackRepo(db)
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    reimbursement_type = request.args.get("type") or None
    if reimbursement_type:
        reimbursement_type = reimbursement_type.upper()
    rows = pathtrack_repo.list_for_sub_cdc(
        sub_cdc_id=session["sub_cdc_id"],
        year=year,
        month=month,
        reimbursement_type=reimbursement_type,
    )
    return render_template(
        "admin/history.html",
        rows=rows,
        year=year, month=month, type=reimbursement_type,
        month_names=_MONTH_NAMES_IT,
    )


@bp.route("/export", methods=["GET"], endpoint="export")
@login_required
@admin_required
def _export_stub():
    return "export - not yet implemented", 501
