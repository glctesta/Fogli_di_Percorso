"""Route per la dichiarazione mensile."""
from __future__ import annotations

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request,
    session, url_for,
)

from fdp_app.auth.decorators import login_required
from fdp_app.db import get_request_db
from fdp_app.pathtracks.deadline import is_open_for_month, previous_month_first_day
from fdp_app.pathtracks.service import (
    DuplicateDeclarationError,
    InvalidInputError,
    NoActiveCoordinateError,
    NoRateConfiguredError,
    PathTrackService,
)
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


def _build_service() -> PathTrackService:
    db = current_app.config["_db"]
    return PathTrackService(
        coordinate_repo=CoordinateRepo(db),
        rate_repo=RateRepo(db),
        registry_repo=RegistryRepo(db),
        pathtrack_repo=PathTrackRepo(db),
        doc_repo=PathTrackDocRepo(db),
        connection_factory=get_request_db,
    )


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


@bp.route("/new", methods=["POST"])
@login_required
def create():
    target_month = previous_month_first_day()
    if not is_open_for_month(target_month):
        flash("Periodo di inserimento chiuso.", "danger")
        return redirect(url_for("dashboard.index"))

    reimbursement_type = (request.form.get("reimbursement_type") or "").strip().upper()
    if reimbursement_type not in ("CARBURANTE", "TAXI"):
        flash("Tipo rimborso non valido.", "danger")
        return redirect(url_for("pathtracks.new"))

    try:
        number_of_trips = int(request.form.get("number_of_trips") or "")
    except ValueError:
        flash("Numero viaggi non valido.", "danger")
        return redirect(url_for("pathtracks.new"))

    sheet_file = request.files.get("sheet_pdf")
    receipt_files = request.files.getlist("receipt_pdf")

    max_bytes = current_app.config["_settings_cls"].UPLOAD_MAX_BYTES
    max_files = current_app.config["_settings_cls"].UPLOAD_MAX_FILES_PER_PATHTRACK

    if not sheet_file or not sheet_file.filename:
        flash("Foglio di percorso (PDF) obbligatorio.", "danger")
        return redirect(url_for("pathtracks.new"))
    sheet_bytes = sheet_file.read()
    if len(sheet_bytes) > max_bytes:
        flash("Foglio di percorso troppo grande (max 5 MB).", "danger")
        return redirect(url_for("pathtracks.new"))

    receipt_bytes_list = []
    for f in receipt_files:
        if f and f.filename:
            data = f.read()
            if len(data) > max_bytes:
                flash(f"Ricevuta '{f.filename}' troppo grande (max 5 MB).", "danger")
                return redirect(url_for("pathtracks.new"))
            receipt_bytes_list.append(data)

    if not receipt_bytes_list:
        flash("Almeno una ricevuta (PDF) obbligatoria.", "danger")
        return redirect(url_for("pathtracks.new"))

    if len(receipt_bytes_list) + 1 > max_files:
        flash(f"Troppi file caricati (max {max_files}).", "danger")
        return redirect(url_for("pathtracks.new"))

    service = _build_service()

    try:
        if reimbursement_type == "CARBURANTE":
            new_id = service.create_fuel(
                employee_hire_history_id=session["user_id"],
                full_name=session["full_name"],
                date_path_track=target_month,
                number_of_trips=number_of_trips,
                sheet_pdf=sheet_bytes,
                receipt_pdfs=receipt_bytes_list,
            )
        else:
            taxi_amounts_raw = request.form.getlist("taxi_amount")
            try:
                taxi_amounts = [float(a) for a in taxi_amounts_raw if a.strip()]
            except ValueError:
                flash("Importi ricevute non validi.", "danger")
                return redirect(url_for("pathtracks.new"))
            new_id = service.create_taxi(
                employee_hire_history_id=session["user_id"],
                full_name=session["full_name"],
                date_path_track=target_month,
                number_of_trips=number_of_trips,
                receipt_amounts=taxi_amounts,
                sheet_pdf=sheet_bytes,
                receipt_pdfs=receipt_bytes_list,
            )

        current_app.logger.info(
            "PathTrack created: user_id=%s id=%s type=%s",
            session["user_id"], new_id, reimbursement_type,
        )
        flash("Dichiarazione mensile salvata.", "success")
        return redirect(url_for("pathtracks.view", path_track_id=new_id))
    except NoActiveCoordinateError:
        flash("Definisci prima il punto di partenza nella mappa.", "warning")
        return redirect(url_for("coordinates.index"))
    except NoRateConfiguredError:
        current_app.logger.error("No rate configured for %s", target_month)
        flash("Rate non configurato per il mese. Contattare l'amministratore.", "danger")
        return redirect(url_for("pathtracks.new"))
    except DuplicateDeclarationError:
        flash("Esiste gia' una dichiarazione attiva per il mese.", "warning")
        return redirect(url_for("pathtracks.new"))
    except InvalidInputError as e:
        flash(str(e), "danger")
        return redirect(url_for("pathtracks.new"))


# Stub temporanei per Tasks 13-16
@bp.route("/<int:path_track_id>", methods=["GET"], endpoint="view")
@login_required
def _view_stub(path_track_id):
    return f"View {path_track_id} - not implemented", 501


@bp.route("", methods=["GET"], endpoint="list_mine")
@login_required
def _list_stub():
    return "List - not implemented", 501
