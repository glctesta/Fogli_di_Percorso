"""Route amministrative (rappresentanza colleghi + storico + export)."""
from __future__ import annotations

from datetime import date as _date, datetime as _datetime

from flask import (
    Blueprint, Response, abort, current_app, flash, redirect, render_template,
    request, session, url_for,
)
from fdp_app.repos.doc_repo import PathTrackDocRepo

from fdp_app.admin.service import build_xlsx
from fdp_app.auth.decorators import admin_required, login_required
from fdp_app.repos.bnr_rate_repo import BnrRateRepo
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


@bp.route("/bnr-rates", methods=["GET"])
@login_required
@admin_required
def bnr_rates():
    db = current_app.config["_db"]
    repo = BnrRateRepo(db)
    standards = repo.list_standards()
    recent = repo.list_recent(limit=20)
    return render_template(
        "admin/bnr_rates.html",
        standards=standards,
        recent=recent,
    )


@bp.route("/bnr-rates", methods=["POST"])
@login_required
@admin_required
def bnr_rates_create():
    db = current_app.config["_db"]
    repo = BnrRateRepo(db)
    try:
        rate_value = float(request.form.get("rate_value") or "")
    except ValueError:
        flash("Valore tasso non valido.", "danger")
        return redirect(url_for("admin.bnr_rates"))
    if rate_value <= 0:
        flash("Tasso deve essere positivo.", "danger")
        return redirect(url_for("admin.bnr_rates"))
    valid_from_raw = request.form.get("valid_from") or ""
    valid_to_raw = request.form.get("valid_to") or ""
    try:
        valid_from = _date.fromisoformat(valid_from_raw)
    except ValueError:
        flash("Data 'valido da' non valida.", "danger")
        return redirect(url_for("admin.bnr_rates"))
    valid_to = None
    if valid_to_raw:
        try:
            valid_to = _date.fromisoformat(valid_to_raw)
        except ValueError:
            flash("Data 'valido fino a' non valida.", "danger")
            return redirect(url_for("admin.bnr_rates"))
    repo.insert(
        rate_value_ron_per_eur=rate_value,
        source="STANDARD",
        valid_from=valid_from,
        valid_to=valid_to,
        is_standard=True,
        user_sys=session.get("full_name") or "admin",
    )
    current_app.logger.info(
        "BNR standard rate inserted: user_id=%s rate=%s from=%s to=%s",
        session.get("user_id"), rate_value, valid_from, valid_to,
    )
    flash(f"Tasso standard inserito (rate={rate_value:.4f}).", "success")
    return redirect(url_for("admin.bnr_rates"))


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
