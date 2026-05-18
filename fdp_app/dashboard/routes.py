"""Stub temporaneo - sara' completato in Task 11."""
from flask import Blueprint

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
def index():
    """Placeholder route. Replaced in Task 11."""
    return "dashboard placeholder"
