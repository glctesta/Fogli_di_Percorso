"""Helpers di autorizzazione: risoluzione del 'target employee' per
la modalita' rappresentanza (?on_behalf_of=...)."""
from __future__ import annotations

from flask import abort, current_app, request, session

from fdp_app.repos.employee_repo import EmployeeRepo, RepresentableEmployee


def resolve_target_employee(default_employee_id: int) -> tuple[int, int | None, RepresentableEmployee | None]:
    """Determines on whose behalf the action is being performed.

    Returns (target_id, in_behalf_of_id, target_employee_obj):
    - target_id: ID of the employee the action operates ON
    - in_behalf_of_id: None when target == logged-in user; the target_id when delegated
    - target_employee_obj: the RepresentableEmployee object (with name) when delegated, None otherwise

    Reads `on_behalf_of` from request.args OR request.form (in that order).
    Validates the requesting user can represent the target. Aborts 403 if not.
    Aborts 400 if the value is non-numeric.
    """
    raw = request.args.get("on_behalf_of") or request.form.get("on_behalf_of")
    if not raw:
        return default_employee_id, None, None
    try:
        target_id = int(raw)
    except ValueError:
        abort(400)

    if target_id == default_employee_id:
        return default_employee_id, None, None

    db = current_app.config["_db"]
    employee_repo = EmployeeRepo(db)
    representables = employee_repo.find_representable_for(
        sub_cdc_id=session["sub_cdc_id"],
        min_function_code=current_app.config["_settings_cls"].MIN_FUNCTION_CODE_FOR_LOGIN,
    )
    target = next(
        (r for r in representables if r.employee_hire_history_id == target_id),
        None,
    )
    if target is None:
        abort(403)

    return target_id, target_id, target
