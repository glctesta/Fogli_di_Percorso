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


@bp.route("/<int:path_track_id>", methods=["GET"])
@login_required
def view(path_track_id: int):
    from flask import abort
    pathtrack_repo = PathTrackRepo(current_app.config["_db"])
    row = pathtrack_repo.find_by_id(
        path_track_id=path_track_id,
        employee_hire_history_id=session["user_id"],
    )
    if row is None:
        abort(404)
    doc_repo = PathTrackDocRepo(current_app.config["_db"])
    docs = doc_repo.list_for_pathtrack(path_track_id=path_track_id)

    target_month = row.date_path_track
    can_edit = is_open_for_month(target_month)
    return render_template(
        "pathtracks/view.html",
        row=row,
        docs=docs,
        month_label=_MONTH_NAMES_IT[target_month.month],
        can_edit=can_edit,
    )


@bp.route("/docs/<int:doc_id>/download", methods=["GET"])
@login_required
def download_doc(doc_id: int):
    from flask import abort, Response
    doc_repo = PathTrackDocRepo(current_app.config["_db"])
    pathtrack_repo = PathTrackRepo(current_app.config["_db"])
    try:
        pdf_bytes, title = doc_repo.get_blob(doc_id=doc_id)
    except FileNotFoundError:
        abort(404)
    # Ownership check (O(n*m); ottimizzazione in Piano 4)
    own_path_tracks = pathtrack_repo.list_for_employee(
        employee_hire_history_id=session["user_id"]
    )
    own_doc_ids = set()
    for pt in own_path_tracks:
        for d in doc_repo.list_for_pathtrack(path_track_id=pt.path_track_id):
            own_doc_ids.add(d.doc_id)
    if doc_id not in own_doc_ids:
        abort(404)
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{title}.pdf"'},
    )


@bp.route("/<int:path_track_id>/delete", methods=["POST"])
@login_required
def delete(path_track_id: int):
    from flask import abort
    pathtrack_repo = PathTrackRepo(current_app.config["_db"])
    row = pathtrack_repo.find_by_id(
        path_track_id=path_track_id,
        employee_hire_history_id=session["user_id"],
    )
    if row is None:
        abort(404)

    if not is_open_for_month(row.date_path_track):
        flash("Periodo di modifica chiuso. Cancellazione non consentita.", "danger")
        return redirect(url_for("pathtracks.view", path_track_id=path_track_id))

    ok = pathtrack_repo.soft_delete(
        path_track_id=path_track_id,
        employee_hire_history_id=session["user_id"],
    )
    if ok:
        doc_repo = PathTrackDocRepo(current_app.config["_db"])
        doc_repo.soft_delete_all_for_pathtrack(path_track_id=path_track_id)
        current_app.logger.info(
            "PathTrack deleted: user_id=%s id=%s", session["user_id"], path_track_id
        )
        flash("Dichiarazione cancellata.", "success")
    else:
        flash("Impossibile cancellare (record non trovato o gia' cancellato).", "warning")
    return redirect(url_for("pathtracks.list_mine"))


@bp.route("", methods=["GET"])
@login_required
def list_mine():
    pathtrack_repo = PathTrackRepo(current_app.config["_db"])
    rows = pathtrack_repo.list_for_employee(
        employee_hire_history_id=session["user_id"],
    )
    return render_template(
        "pathtracks/list.html",
        rows=rows,
        month_names=_MONTH_NAMES_IT,
    )
