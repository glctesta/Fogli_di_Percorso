"""Route per la dichiarazione mensile."""
from __future__ import annotations

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request,
    session, url_for,
)

from fdp_app.auth.decorators import login_required
from fdp_app.pathtracks.deadline import is_open_for_month, previous_month_first_day
from fdp_app.repos.coordinate_repo import CoordinateRepo
from fdp_app.repos.doc_repo import PathTrackDocRepo
from fdp_app.repos.pathtrack_repo import PathTrackRepo
from fdp_app.repos.rate_repo import RateRepo
from fdp_app.repos.registry_repo import RegistryRepo

bp = Blueprint("pathtracks", __name__, url_prefix="/pathtracks")

_MONTH_NAMES_IT = [
    "", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]


@bp.route("/new", methods=["GET"])
@login_required
def new():
    coord_repo = CoordinateRepo(current_app.config["_db"])
    coord = coord_repo.find_active(session["user_id"])
    if coord is None:
        flash(
            "Definisci prima il punto di partenza nella mappa.",
            "warning",
        )
        return redirect(url_for("coordinates.index"))

    target_month = previous_month_first_day()
    if not is_open_for_month(target_month):
        flash(
            f"Il periodo di inserimento per {_MONTH_NAMES_IT[target_month.month]} "
            f"{target_month.year} e' chiuso (scadenza superata).",
            "danger",
        )
        return redirect(url_for("dashboard.index"))

    pathtrack_repo = PathTrackRepo(current_app.config["_db"])
    existing = pathtrack_repo.find_active_for_month(
        employee_hire_history_id=session["user_id"],
        date_path_track=target_month,
    )
    if existing is not None:
        return redirect(url_for("pathtracks.view", path_track_id=existing.path_track_id))

    rate_repo = RateRepo(current_app.config["_db"])
    rate = rate_repo.find_for_date(target_month)

    return render_template(
        "pathtracks/new.html",
        target_month=target_month,
        month_label=_MONTH_NAMES_IT[target_month.month],
        coord=coord,
        rate=rate,
    )


# Stub temporanei per Tasks 13-16
@bp.route("/<int:path_track_id>", methods=["GET"], endpoint="view")
@login_required
def _view_stub(path_track_id):
    return f"View {path_track_id} - not implemented", 501


@bp.route("", methods=["GET"], endpoint="list_mine")
@login_required
def _list_stub():
    return "List - not implemented", 501
