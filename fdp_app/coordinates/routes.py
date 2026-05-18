"""Route per la gestione del punto di partenza."""
from __future__ import annotations

from flask import (
    Blueprint, current_app, render_template, session,
)

from fdp_app.auth.decorators import login_required
from fdp_app.coordinates.service import CoordinateService
from fdp_app.pathtracks.routing import RoutingClient
from fdp_app.repos.coordinate_repo import CoordinateRepo

bp = Blueprint("coordinates", __name__)


def _build_service() -> CoordinateService:
    s = current_app.config["_settings_cls"]
    db = current_app.config["_db"]
    repo = CoordinateRepo(db)
    routing = RoutingClient(
        osrm_base=s.OSRM_BASE,
        ors_base=s.ORS_BASE,
        ors_api_key=s.ORS_API_KEY,
    )
    return CoordinateService(repo=repo, routing=routing, workplace=s.workplace())


@bp.route("/coordinates", methods=["GET"])
@login_required
def index():
    service = _build_service()
    active = service.find_active(session["user_id"])
    workplace = current_app.config["_settings_cls"].workplace()
    return render_template(
        "coordinates/index.html",
        active=active,
        workplace=workplace,
    )


# Stub temporanei - implementazione reale in Task 10
@bp.route("/coordinates", methods=["POST"], endpoint="create")
@login_required
def _create_stub():
    return "Not yet implemented", 501


@bp.route("/coordinates/delete", methods=["POST"], endpoint="delete")
@login_required
def _delete_stub():
    return "Not yet implemented", 501
