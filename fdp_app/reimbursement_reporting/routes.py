"""Route per raccolta informazioni aggiuntive e report rimborsi."""
from __future__ import annotations

from datetime import date as _date

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_babel import _

from fdp_app.auth.decorators import login_required, reimbursement_reporting_required
from fdp_app.reimbursement_reporting.service import (
    build_reimbursement_xlsx,
    effective_reimbursement,
)
from fdp_app.repos.reimbursement_reporting_repo import ReimbursementReportingRepo

bp = Blueprint(
    "reimbursement_reporting",
    __name__,
    url_prefix="/reimbursement-reporting",
)


def _apply_non_zero_filter(rows, non_zero_only: bool):
    if not non_zero_only:
        return rows
    return [r for r in rows if abs(effective_reimbursement(r)) > 0.000001]


@bp.route("", methods=["GET"])
@login_required
@reimbursement_reporting_required
def index():
    today = _date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month
    if not 1 <= month <= 12:
        abort(400)

    repo = ReimbursementReportingRepo(current_app.config["_db"])
    all_rows = repo.list_month_summary(
        sub_cdc_id=session["sub_cdc_id"],
        year=year,
        month=month,
    )
    non_zero_only = request.args.get("non_zero_only") == "1"
    rows = _apply_non_zero_filter(all_rows, non_zero_only)
    selected_employee_id = request.args.get("employee_id", type=int)
    selected_row = None
    if selected_employee_id is not None:
        selected_row = next(
            (r for r in all_rows if r.employee_hire_history_id == selected_employee_id),
            None,
        )
        if selected_row is None:
            abort(404)

        # Keep the selected employee visible while editing even if the active
        # filter would otherwise exclude it (for example after reducing the
        # effective reimbursement to zero).
        if non_zero_only and all(
            row.employee_hire_history_id != selected_employee_id for row in rows
        ):
            rows = [selected_row, *rows]

    return render_template(
        "reimbursement_reporting/index.html",
        rows=rows,
        year=year,
        month=month,
        selected_employee_id=selected_employee_id,
        selected_row=selected_row,
        non_zero_only=non_zero_only,
        effective_reimbursement=effective_reimbursement,
    )


@bp.route("/adjustments", methods=["POST"])
@login_required
@reimbursement_reporting_required
def save_adjustment():
    year = request.form.get("year", type=int)
    month = request.form.get("month", type=int)
    employee_id = request.form.get("employee_id", type=int)

    if not year or not month or not employee_id or not (1 <= month <= 12):
        abort(400)

    additional_raw = (request.form.get("additional_amount_eur") or "0").strip().replace(",", ".")
    deduction_raw = (request.form.get("deduction_amount_eur") or "0").strip().replace(",", ".")
    notes = (request.form.get("notes") or "").strip()
    non_zero_only = request.form.get("non_zero_only") == "1"

    try:
        additional = float(additional_raw)
        deduction = float(deduction_raw)
    except ValueError:
        flash(_("Valori integrazione/detrazione non validi."), "danger")
        return redirect(
            url_for(
                "reimbursement_reporting.index",
                year=year,
                month=month,
                non_zero_only=1 if non_zero_only else None,
            )
        )

    if additional < 0 or deduction < 0:
        flash(_("Integrazione e detrazione devono essere >= 0."), "danger")
        return redirect(
            url_for(
                "reimbursement_reporting.index",
                year=year,
                month=month,
                non_zero_only=1 if non_zero_only else None,
            )
        )

    repo = ReimbursementReportingRepo(current_app.config["_db"])
    rows = repo.list_month_summary(
        sub_cdc_id=session["sub_cdc_id"],
        year=year,
        month=month,
    )
    if employee_id not in {r.employee_hire_history_id for r in rows}:
        abort(404)

    repo.upsert_adjustment(
        employee_hire_history_id=employee_id,
        sub_cdc_id=session["sub_cdc_id"],
        year=year,
        month=month,
        additional_amount_eur=additional,
        deduction_amount_eur=deduction,
        notes=notes,
        user_sys=session.get("full_name") or "reporting",
    )
    flash(_("Informazioni aggiuntive salvate."), "success")
    return redirect(
        url_for(
            "reimbursement_reporting.index",
            year=year,
            month=month,
            employee_id=employee_id,
            non_zero_only=1 if non_zero_only else None,
        )
    )


@bp.route("/export", methods=["GET"])
@login_required
@reimbursement_reporting_required
def export_all():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    if not year or not month or not (1 <= month <= 12):
        abort(400)

    repo = ReimbursementReportingRepo(current_app.config["_db"])
    rows = repo.list_month_summary(
        sub_cdc_id=session["sub_cdc_id"],
        year=year,
        month=month,
    )
    non_zero_only = request.args.get("non_zero_only") == "1"
    rows = _apply_non_zero_filter(rows, non_zero_only)
    xlsx = build_reimbursement_xlsx(
        rows,
        year=year,
        month=month,
        sheet_name=f"Rimborsi-{year}-{month:02d}",
    )
    suffix = "-nonzero" if non_zero_only else ""
    filename = f"rimborso-effettivo-{year:04d}-{month:02d}{suffix}.xlsx"
    return Response(
        xlsx,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@bp.route("/export/<int:employee_hire_history_id>", methods=["GET"])
@login_required
@reimbursement_reporting_required
def export_employee(employee_hire_history_id: int):
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    if not year or not month or not (1 <= month <= 12):
        abort(400)

    repo = ReimbursementReportingRepo(current_app.config["_db"])
    rows = repo.list_month_summary(
        sub_cdc_id=session["sub_cdc_id"],
        year=year,
        month=month,
    )
    non_zero_only = request.args.get("non_zero_only") == "1"
    selected = [r for r in rows if r.employee_hire_history_id == employee_hire_history_id]
    selected = _apply_non_zero_filter(selected, non_zero_only)
    if not selected:
        abort(404)

    xlsx = build_reimbursement_xlsx(
        selected,
        year=year,
        month=month,
        sheet_name=f"Utente-{employee_hire_history_id}",
    )
    suffix = "-nonzero" if non_zero_only else ""
    filename = (
        f"rimborso-utente-{employee_hire_history_id}-{year:04d}-{month:02d}{suffix}.xlsx"
    )
    return Response(
        xlsx,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
