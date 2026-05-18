"""Route per la gestione del punto di partenza."""
from __future__ import annotations

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request,
    session, url_for,
)

from fdp_app.auth.decorators import login_required
from fdp_app.coordinates.service import (
    ActiveCoordinateAlreadyExists,
    CoordinateService,
)
from fdp_app.pathtracks.routing import RoutingError
from fdp_app.repos.coordinate_repo import CoordinateRepo

bp = Blueprint("coordinates", __name__)


def _build_service() -> CoordinateService:
    db = current_app.config["_db"]
    repo = CoordinateRepo(db)
    routing = current_app.config["_routing"]
    workplace = current_app.config["_workplace"]
    return CoordinateService(repo=repo, routing=routing, workplace=workplace)


@bp.route("/coordinates", methods=["GET"])
@login_required
def index():
    service = _build_service()
    active = service.find_active(session["user_id"])
    workplace = current_app.config["_workplace"]
    return render_template(
        "coordinates/index.html",
        active=active,
        workplace=workplace,
    )


@bp.route("/coordinates", methods=["POST"])
@login_required
def create():
    try:
        lat = float(request.form.get("lat") or "")
        lon = float(request.form.get("lon") or "")
    except ValueError:
        flash("Coordinate non valide.", "danger")
        return redirect(url_for("coordinates.index"))

    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        flash("Coordinate non valide (lat/lon fuori range).", "danger")
        return redirect(url_for("coordinates.index"))

    label = (request.form.get("label") or "").strip()
    if not label:
        flash("Etichetta obbligatoria.", "danger")
        return redirect(url_for("coordinates.index"))
    if len(label) > 200:
        label = label[:200]

    service = _build_service()
    try:
        new_id = service.create(
            employee_hire_history_id=session["user_id"],
            label=label,
            lat=lat,
            lon=lon,
        )
        current_app.logger.info(
            "Coordinate created: user_id=%s coord_id=%s",
            session["user_id"], new_id,
        )
        flash("Punto di partenza salvato.", "success")
    except ActiveCoordinateAlreadyExists:
        flash(
            "Esiste gia' un punto attivo. Cancellarlo prima di crearne uno nuovo.",
            "danger",
        )
    except RoutingError as e:
        current_app.logger.warning(
            "Routing failure for user_id=%s: %s", session["user_id"], e,
        )
        flash(
            "Servizio mappe temporaneamente non disponibile. Riprovare piu' tardi.",
            "danger",
        )

    return redirect(url_for("coordinates.index"))


@bp.route("/coordinates/delete", methods=["POST"])
@login_required
def delete():
    try:
        coordinate_id = int(request.form.get("coordinate_id") or "")
    except ValueError:
        flash("Identificativo punto non valido.", "danger")
        return redirect(url_for("coordinates.index"))

    service = _build_service()
    ok = service.delete(
        coordinate_id=coordinate_id,
        employee_hire_history_id=session["user_id"],
    )
    if ok:
        current_app.logger.info(
            "Coordinate deleted: user_id=%s coord_id=%s",
            session["user_id"], coordinate_id,
        )
        flash("Punto di partenza cancellato.", "success")
    else:
        flash("Punto non trovato o non posseduto.", "warning")
    return redirect(url_for("coordinates.index"))
