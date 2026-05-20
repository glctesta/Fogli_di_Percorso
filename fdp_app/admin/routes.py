"""Route amministrative (rappresentanza colleghi + storico + export)."""
from __future__ import annotations

from flask import (
    Blueprint, Response, abort, current_app, render_template, request, session,
)
from fdp_app.repos.doc_repo import PathTrackDocRepo

from fdp_app.admin.service import build_xlsx
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


@bp.route("/pathtracks/<int:path_track_id>", methods=["GET"])
@login_required
@admin_required
def view_pathtrack(path_track_id: int):
    db = current_app.config["_db"]
    pathtrack_repo = PathTrackRepo(db)
    row = pathtrack_repo.find_by_id_in_sub_cdc(
        path_track_id=path_track_id,
        sub_cdc_id=session["sub_cdc_id"],
    )
    if row is None:
        abort(404)
    doc_repo = PathTrackDocRepo(db)
    docs = doc_repo.list_for_pathtrack(path_track_id=path_track_id)
    return render_template(
        "admin/view_pathtrack.html",
        row=row,
        docs=docs,
        month_label=_MONTH_NAMES_IT[row.date_path_track.month],
    )


@bp.route("/export", methods=["GET"])
@login_required
@admin_required
def export():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    if not year or not month or not (1 <= month <= 12):
        abort(400)
    db = current_app.config["_db"]
    pathtrack_repo = PathTrackRepo(db)
    rows = pathtrack_repo.list_for_sub_cdc(
        sub_cdc_id=session["sub_cdc_id"],
        year=year,
        month=month,
    )
    xlsx_bytes = build_xlsx(
        rows, year=year, month=month, month_name=_MONTH_NAMES_IT[month],
    )
    filename = f"fogli-di-percorso-{year:04d}-{month:02d}.xlsx"
    return Response(
        xlsx_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
