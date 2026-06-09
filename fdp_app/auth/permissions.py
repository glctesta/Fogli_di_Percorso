"""Permission helpers shared across routes and templates."""
from __future__ import annotations


def _matches_static_whitelist(
    *,
    user_id: int | None,
    function_code: int | None,
    settings_cls,
) -> bool:
    if user_id is None:
        return False
    allowed_ids = set(settings_cls.REIMBURSEMENT_REPORT_ALLOWED_USER_IDS)
    if user_id in allowed_ids:
        return True
    if function_code is None:
        return False
    allowed_function_codes = set(settings_cls.REIMBURSEMENT_REPORT_ALLOWED_FUNCTION_CODES)
    return function_code in allowed_function_codes


def can_access_reimbursement_reporting(
    *,
    user_id: int | None,
    function_code: int | None,
    settings_cls,
    db=None,
) -> bool:
    if _matches_static_whitelist(
        user_id=user_id,
        function_code=function_code,
        settings_cls=settings_cls,
    ):
        return True
    if user_id is None or db is None:
        return False
    try:
        from fdp_app.repos.reimbursement_permission_repo import ReimbursementPermissionRepo

        repo = ReimbursementPermissionRepo(db)
        # Be strict: treat only explicit boolean True as allowed.
        # This avoids accidental truthy mocks in tests.
        return repo.is_allowed(
            user_id=user_id,
            function_code=function_code,
        ) is True
    except Exception:
        # If the table is missing or DB is unavailable, keep env-based fallback only.
        return False
