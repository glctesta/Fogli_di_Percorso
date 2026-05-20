"""Route per la dichiarazione mensile (workflow DRAFT/SUBMITTED)."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template, request,
    session, url_for, Response,
)

from flask_babel import _

from fdp_app.auth.decorators import login_required
from fdp_app.admin.helpers import resolve_target_employee
from fdp_app.db import get_request_db
from fdp_app.pathtracks.deadline import (
    can_create_draft_for,
    can_submit_for,
    previous_month_first_day,
)
from fdp_app.pathtracks.service import (
    DeadlineClosedError,
    DuplicateDeclarationError,
    InvalidInputError,
    NoActiveCoordinateError,
    NoRateConfiguredError,
    NotADraftError,
    PathTrackService,
)
from fdp_app.pathtracks.bnr_client import BnrRateClient
from fdp_app.pathtracks.currency import CurrencyService
from fdp_app.repos.bnr_rate_repo import BnrRateRepo
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
    bnr_client = current_app.config.get("_bnr_client") or BnrRateClient()
    return PathTrackService(
        coordinate_repo=CoordinateRepo(db),
        rate_repo=RateRepo(db),
        registry_repo=RegistryRepo(db),
        pathtrack_repo=PathTrackRepo(db),
        doc_repo=PathTrackDocRepo(db),
        connection_factory=get_request_db,
        currency_service=CurrencyService(
            bnr_repo=BnrRateRepo(db),
            bnr_client=bnr_client,
        ),
    )


def _parse_pdf_uploads(max_bytes, max_files):
    """Estrae sheet_pdf (bytes) e receipt_pdfs (lista bytes) dal form,
    fa size check + magic bytes. Ritorna (sheet_bytes, receipts_list) o
    solleva un dict-like errore via flash + redirect (caller deve poi return).

    Convenzione: ritorna (None, None, error_message) in caso di errore.
    """
    sheet_file = request.files.get("sheet_pdf")
    receipt_files = request.files.getlist("receipt_pdf")

    if not sheet_file or not sheet_file.filename:
        return None, None, _("Foglio di percorso (PDF) obbligatorio.")
    sheet_bytes = sheet_file.read()
    if len(sheet_bytes) > max_bytes:
        return None, None, _("Foglio di percorso troppo grande (max 5 MB).")
    if not sheet_bytes.startswith(b"%PDF-"):
        return None, None, _("Il foglio di percorso non e' un PDF valido.")

    receipts = []
    for f in receipt_files:
        if f and f.filename:
            data = f.read()
            if len(data) > max_bytes:
                return None, None, _("Ricevuta '%(filename)s' troppo grande (max 5 MB).", filename=f.filename)
            receipts.append(data)

    if not receipts:
        return None, None, _("Almeno una ricevuta (PDF) obbligatoria.")

    if len(receipts) + 1 > max_files:
        return None, None, f"Troppi file caricati (max {max_files})."

    return sheet_bytes, receipts, None


def _parse_taxi_amounts():
    raw = request.form.getlist("taxi_amount")
    try:
        amounts = [float(a) for a in raw if a and a.strip()]
    except ValueError:
        return None
    return amounts


# ---- GET / new -------------------------------------------------------------

@bp.route("/new", methods=["GET"])
@login_required
def new():
    target_id, in_behalf_of, target = resolve_target_employee(session["user_id"])
    coord_repo = CoordinateRepo(current_app.config["_db"])
    coord = coord_repo.find_active(target_id)
    if coord is None:
        flash(_("Definisci prima il punto di partenza nella mappa."), "warning")
        if in_behalf_of:
            return redirect(url_for("coordinates.index", on_behalf_of=in_behalf_of))
        return redirect(url_for("coordinates.index"))

    # Mese di riferimento: di default il mese precedente; se siamo nel mese
    # corrente e l'utente puo' iniziare a lavorare in anticipo, mostriamo
    # anche un selettore (per ora MVP: solo mese precedente, fallback corrente)
    target_month = previous_month_first_day()
    # Se siamo nel mese 1-5 del successivo, target=previous (default).
    # Altrimenti, target=current month
    today = datetime.now(ZoneInfo("Europe/Rome")).date()
    if not can_create_draft_for(target_month):
        # Il mese precedente non e' piu' modificabile, usiamo il corrente
        target_month = today.replace(day=1)

    if not can_create_draft_for(target_month):
        flash(_("Periodo di inserimento chiuso."), "danger")
        return redirect(url_for("pathtracks.list_mine"))

    pathtrack_repo = PathTrackRepo(current_app.config["_db"])
    existing = pathtrack_repo.find_active_for_month(
        employee_hire_history_id=target_id,
        date_path_track=target_month,
    )
    if existing is not None:
        return redirect(url_for("pathtracks.view", path_track_id=existing.path_track_id))

    rate_repo = RateRepo(current_app.config["_db"])
    rate = rate_repo.find_for_date(target_month)

    can_submit_now = can_submit_for(target_month)

    return render_template(
        "pathtracks/new.html",
        target_month=target_month,
        month_label=_MONTH_NAMES_IT[target_month.month],
        coord=coord,
        rate=rate,
        can_submit_now=can_submit_now,
        on_behalf_of=in_behalf_of,
        target=target,
    )


# ---- POST / new (create draft, maybe submit) ------------------------------

@bp.route("/new", methods=["POST"])
@login_required
def create():
    target_id, in_behalf_of, target = resolve_target_employee(session["user_id"])

    action = (request.form.get("action") or "draft").strip().lower()
    if action not in ("draft", "submit"):
        flash(_("Azione non riconosciuta."), "danger")
        return redirect(url_for("pathtracks.new", on_behalf_of=in_behalf_of) if in_behalf_of
                        else url_for("pathtracks.new"))

    target_month = previous_month_first_day()
    today = datetime.now(ZoneInfo("Europe/Rome")).date()
    if not can_create_draft_for(target_month):
        target_month = today.replace(day=1)

    reimbursement_type = (request.form.get("reimbursement_type") or "").strip().upper()
    if reimbursement_type not in ("CARBURANTE", "TAXI"):
        flash(_("Tipo rimborso non valido."), "danger")
        return redirect(url_for("pathtracks.new", on_behalf_of=in_behalf_of) if in_behalf_of
                        else url_for("pathtracks.new"))

    try:
        number_of_trips = int(request.form.get("number_of_trips") or "")
    except ValueError:
        flash(_("Numero viaggi non valido."), "danger")
        return redirect(url_for("pathtracks.new", on_behalf_of=in_behalf_of) if in_behalf_of
                        else url_for("pathtracks.new"))

    s = current_app.config["_settings_cls"]
    sheet_bytes, receipt_bytes_list, error = _parse_pdf_uploads(
        s.UPLOAD_MAX_BYTES, s.UPLOAD_MAX_FILES_PER_PATHTRACK
    )
    if error:
        flash(error, "danger")
        return redirect(url_for("pathtracks.new", on_behalf_of=in_behalf_of) if in_behalf_of
                        else url_for("pathtracks.new"))

    service = _build_service()

    try:
        if reimbursement_type == "CARBURANTE":
            new_id = service.create_draft_fuel(
                employee_hire_history_id=session["user_id"],
                date_path_track=target_month,
                number_of_trips=number_of_trips,
                sheet_pdf=sheet_bytes,
                receipt_pdfs=receipt_bytes_list,
                in_behalf_of_id=in_behalf_of,
            )
        else:
            taxi_amounts = _parse_taxi_amounts()
            if taxi_amounts is None:
                flash(_("Importi ricevute non validi."), "danger")
                return redirect(url_for("pathtracks.new", on_behalf_of=in_behalf_of) if in_behalf_of
                                else url_for("pathtracks.new"))
            new_id = service.create_draft_taxi(
                employee_hire_history_id=session["user_id"],
                date_path_track=target_month,
                number_of_trips=number_of_trips,
                receipt_amounts=taxi_amounts,
                sheet_pdf=sheet_bytes,
                receipt_pdfs=receipt_bytes_list,
                in_behalf_of_id=in_behalf_of,
            )

        current_app.logger.info(
            "PathTrack DRAFT created: user_id=%s id=%s type=%s in_behalf_of=%s",
            session["user_id"], new_id, reimbursement_type, in_behalf_of,
        )

        if action == "submit":
            try:
                registry_id, bnr_resolved = service.submit(
                    path_track_id=new_id,
                    employee_hire_history_id=session["user_id"],
                    full_name=session["full_name"],
                )
                current_app.logger.info(
                    "PathTrack SUBMITTED: user_id=%s id=%s registry_id=%s bnr_resolved=%s",
                    session["user_id"], new_id, registry_id, bnr_resolved,
                )
                flash(
                    _("Dichiarazione inviata con successo. RegistryId: %(rid)s", rid=registry_id),
                    "success",
                )
                if not bnr_resolved:
                    flash(
                        _("Tasso di cambio BNR non disponibile al momento dell'invio; il campo RON sara' vuoto."),
                        "warning",
                    )
            except DeadlineClosedError as e:
                flash(
                    _("Bozza salvata ma non inviata: %(error)s. Potrai inviarla dal 1 al 5 del mese successivo.", error=e),
                    "warning",
                )
        else:
            flash(_("Bozza salvata. La potrai aggiornare fino al 5 del mese successivo."), "success")

        return redirect(url_for("pathtracks.view", path_track_id=new_id))
    except NoActiveCoordinateError:
        flash(_("Definisci prima il punto di partenza nella mappa."), "warning")
        return redirect(url_for("coordinates.index", on_behalf_of=in_behalf_of) if in_behalf_of
                        else url_for("coordinates.index"))
    except NoRateConfiguredError:
        current_app.logger.error("No rate configured for %s", target_month)
        flash(_("Rate non configurato per il mese. Contattare l'amministratore."), "danger")
        return redirect(url_for("pathtracks.new", on_behalf_of=in_behalf_of) if in_behalf_of
                        else url_for("pathtracks.new"))
    except DuplicateDeclarationError:
        flash(_("Esiste gia' una dichiarazione attiva per il mese."), "warning")
        return redirect(url_for("pathtracks.new", on_behalf_of=in_behalf_of) if in_behalf_of
                        else url_for("pathtracks.new"))
    except DeadlineClosedError as e:
        flash(str(e), "danger")
        return redirect(url_for("pathtracks.list_mine"))
    except InvalidInputError as e:
        flash(str(e), "danger")
        return redirect(url_for("pathtracks.new", on_behalf_of=in_behalf_of) if in_behalf_of
                        else url_for("pathtracks.new"))


# ---- GET /<id> view --------------------------------------------------------

@bp.route("/<int:path_track_id>", methods=["GET"])
@login_required
def view(path_track_id: int):
    pathtrack_repo = PathTrackRepo(current_app.config["_db"])
    row = pathtrack_repo.find_by_id(
        path_track_id=path_track_id,
        employee_hire_history_id=session["user_id"],
    )
    if row is None:
        abort(404)
    doc_repo = PathTrackDocRepo(current_app.config["_db"])
    docs = doc_repo.list_for_pathtrack(path_track_id=path_track_id)

    rate = None
    if row.status == "DRAFT":
        rate_repo = RateRepo(current_app.config["_db"])
        rate = rate_repo.find_for_date(row.date_path_track)

    can_edit = (row.status == "DRAFT") and can_create_draft_for(row.date_path_track)
    can_submit = (row.status == "DRAFT") and can_submit_for(row.date_path_track)

    return render_template(
        "pathtracks/view.html",
        row=row,
        docs=docs,
        rate=rate,
        month_label=_MONTH_NAMES_IT[row.date_path_track.month],
        can_edit=can_edit,
        can_submit=can_submit,
    )


# ---- POST /<id>/update -----------------------------------------------------

@bp.route("/<int:path_track_id>/update", methods=["POST"])
@login_required
def update(path_track_id: int):
    try:
        number_of_trips = int(request.form.get("number_of_trips") or "")
    except ValueError:
        flash(_("Numero viaggi non valido."), "danger")
        return redirect(url_for("pathtracks.view", path_track_id=path_track_id))

    reimbursement_type = (request.form.get("reimbursement_type") or "").strip().upper()

    s = current_app.config["_settings_cls"]
    sheet_bytes, receipt_bytes_list, error = _parse_pdf_uploads(
        s.UPLOAD_MAX_BYTES, s.UPLOAD_MAX_FILES_PER_PATHTRACK
    )
    if error:
        flash(error, "danger")
        return redirect(url_for("pathtracks.view", path_track_id=path_track_id))

    service = _build_service()

    try:
        if reimbursement_type == "CARBURANTE":
            service.update_draft_fuel(
                path_track_id=path_track_id,
                employee_hire_history_id=session["user_id"],
                number_of_trips=number_of_trips,
                sheet_pdf=sheet_bytes,
                receipt_pdfs=receipt_bytes_list,
            )
        elif reimbursement_type == "TAXI":
            taxi_amounts = _parse_taxi_amounts()
            if taxi_amounts is None:
                flash(_("Importi ricevute non validi."), "danger")
                return redirect(url_for("pathtracks.view", path_track_id=path_track_id))
            service.update_draft_taxi(
                path_track_id=path_track_id,
                employee_hire_history_id=session["user_id"],
                number_of_trips=number_of_trips,
                receipt_amounts=taxi_amounts,
                sheet_pdf=sheet_bytes,
                receipt_pdfs=receipt_bytes_list,
            )
        else:
            flash(_("Tipo rimborso non valido."), "danger")
            return redirect(url_for("pathtracks.view", path_track_id=path_track_id))

        current_app.logger.info(
            "PathTrack DRAFT updated: user_id=%s id=%s",
            session["user_id"], path_track_id,
        )
        flash(_("Bozza aggiornata."), "success")
    except NotADraftError as e:
        flash(str(e), "warning")
    except DeadlineClosedError as e:
        flash(str(e), "danger")
    except (NoActiveCoordinateError, NoRateConfiguredError, InvalidInputError) as e:
        flash(str(e), "danger")

    return redirect(url_for("pathtracks.view", path_track_id=path_track_id))


# ---- POST /<id>/submit -----------------------------------------------------

@bp.route("/<int:path_track_id>/submit", methods=["POST"])
@login_required
def submit(path_track_id: int):
    # Force-submit allowed only when user is admin (FC > 60).
    requested_force = (request.form.get("force") == "1")
    is_admin = (session.get("function_code", 0) > 60)
    force = requested_force and is_admin

    service = _build_service()
    try:
        registry_id, bnr_resolved = service.submit(
            path_track_id=path_track_id,
            employee_hire_history_id=session["user_id"],
            full_name=session["full_name"],
            force=force,
        )
        action_log = "SUBMITTED (admin override)" if force else "SUBMITTED"
        current_app.logger.info(
            "PathTrack %s: user_id=%s id=%s registry_id=%s bnr_resolved=%s",
            action_log, session["user_id"], path_track_id, registry_id, bnr_resolved,
        )
        flash(
            _("Dichiarazione inviata con successo. RegistryId: %(rid)s", rid=registry_id)
            + (" (override admin)" if force else ""),
            "success",
        )
        if not bnr_resolved:
            flash(
                _("Tasso di cambio BNR non disponibile al momento dell'invio; il campo RON sara' vuoto."),
                "warning",
            )
    except NotADraftError as e:
        flash(str(e), "warning")
    except DeadlineClosedError as e:
        flash(str(e), "danger")
    return redirect(url_for("pathtracks.view", path_track_id=path_track_id))


# ---- POST /<id>/delete -----------------------------------------------------

@bp.route("/<int:path_track_id>/delete", methods=["POST"])
@login_required
def delete(path_track_id: int):
    pathtrack_repo = PathTrackRepo(current_app.config["_db"])
    row = pathtrack_repo.find_by_id(
        path_track_id=path_track_id,
        employee_hire_history_id=session["user_id"],
    )
    if row is None:
        abort(404)

    if row.status != "DRAFT":
        flash(_("Solo le bozze possono essere cancellate."), "warning")
        return redirect(url_for("pathtracks.view", path_track_id=path_track_id))

    ok = pathtrack_repo.soft_delete(
        path_track_id=path_track_id,
        employee_hire_history_id=session["user_id"],
    )
    if ok:
        doc_repo = PathTrackDocRepo(current_app.config["_db"])
        doc_repo.soft_delete_all_for_pathtrack(path_track_id=path_track_id)
        current_app.logger.info(
            "PathTrack DRAFT deleted: user_id=%s id=%s",
            session["user_id"], path_track_id,
        )
        flash(_("Bozza cancellata."), "success")
    else:
        flash(_("Impossibile cancellare (non e' una bozza o gia' cancellata)."), "warning")
    return redirect(url_for("pathtracks.list_mine"))


# ---- GET / list ------------------------------------------------------------

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


# ---- GET /docs/<id>/download -----------------------------------------------

@bp.route("/docs/<int:doc_id>/download", methods=["GET"])
@login_required
def download_doc(doc_id: int):
    doc_repo = PathTrackDocRepo(current_app.config["_db"])
    try:
        pdf_bytes, title = doc_repo.get_blob(doc_id=doc_id)
    except FileNotFoundError:
        abort(404)

    # Ownership check via single SQL JOIN
    owner = doc_repo.find_owner_employee_for_doc(doc_id=doc_id)
    if owner is None:
        abort(404)
    employee_id, beneficiary_id = owner
    if session["user_id"] not in (employee_id, beneficiary_id):
        # Admin fallback: same SubCdcId?
        if session.get("function_code", 0) > 60:
            sub_cdc_owner = doc_repo.find_sub_cdc_for_doc(doc_id=doc_id)
            if sub_cdc_owner is None or sub_cdc_owner != session.get("sub_cdc_id"):
                abort(404)
        else:
            abort(404)

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{title}.pdf"'},
    )
