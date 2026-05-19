# Fogli di Percorso — Piano 4: Admin / Rappresentanza

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Aggiungere le funzioni amministrative: rappresentanza di colleghi (`InBehalfOfId`), consultazione storico filtrata per `SubCdcId`, export Excel mensile delle dichiarazioni, sblocco bozze scadute per gli admin. Più i fix di follow-up dal final review del Piano 3.

**Architecture:** Nuovo blueprint `admin/` con route `/admin/representable`, `/admin/history`, `/admin/export`. `EmployeeRepo` esteso con `find_representable_for(sub_cdc_id)`. `PathTrackRepo` esteso con `list_for_sub_cdc_id(sub_cdc_id, year, month, type)`. Routes `/coordinates` e `/pathtracks` accettano query string `?on_behalf_of=<id>` valorizzando `InBehalfOfId`. Export XLSX in-memory via `openpyxl`.

**Tech Stack:** Flask, pyodbc, openpyxl (già in requirements).

**Riferimento spec:** §6.4 (rappresentanza), §6.6 (storico/export). Aggiungiamo §7.8 (admin override per submit).

**Prerequisito:** Piano 3.1 completato e taggato `v0.3.1-draft-workflow`. 148 test verdi.

---

## Regole di business

| Aspetto | Regola |
|---|---|
| **Chi può rappresentare** | Utente loggato con `FunctionCode > 60` può rappresentare dipendenti con `FunctionCode < 60` e stesso `SubCdcId` |
| **Visibility scope** | Lo storico admin mostra solo `PathTracks` di dipendenti dello stesso `SubCdcId` (sia per inserimento diretto sia per `InBehalfOfId`) |
| **In rappresentanza**: `InBehalfOfId` = id del rappresentato. `EmployeeHireHistoryId` = utente loggato (chi inserisce) |
| **Admin submit override** | Admin può forzare il submit di una bozza propria o di un rappresentato anche oltre il 5 |
| **Export XLSX** | Una riga per ogni `PathTracks` (DRAFT + SUBMITTED) del SubCdcId nel mese richiesto |

---

## File modificati / creati

**Creati:**
- `fdp_app/admin/__init__.py` (empty)
- `fdp_app/admin/routes.py` — blueprint `/admin/*`
- `fdp_app/admin/service.py` — orchestrazione list/export
- `fdp_app/templates/admin/representable.html`
- `fdp_app/templates/admin/history.html`
- `fdp_app/repos/base_repo.py` — `BaseRepo` con `_open_cursor` riusabile
- `tests/test_admin_routes.py`
- `tests/test_admin_service.py`
- `tests/test_employee_repo_representable.py`
- `tests/test_pathtrack_repo_subcdc.py`
- `sql/003_add_fk_rateid.sql` — opzionale FK su `PathTracks.RateIdUsed` (vedi follow-up review)

**Modificati:**
- `fdp_app/repos/employee_repo.py` — nuovo metodo `find_representable_for(sub_cdc_id) -> list`. `EmployeeRepo` eredita da `BaseRepo`
- `fdp_app/repos/coordinate_repo.py` — eredita da `BaseRepo`
- `fdp_app/repos/pathtrack_repo.py` — eredita da `BaseRepo` + nuovi metodi `list_for_sub_cdc(sub_cdc_id, year=None, month=None, type=None)` e `find_by_id_with_employee(path_track_id)` (per ownership check via JOIN)
- `fdp_app/repos/doc_repo.py` — eredita da `BaseRepo` + nuovo metodo `find_owner_employee_for_doc(doc_id) -> int|None` (SQL JOIN)
- `fdp_app/repos/rate_repo.py`, `registry_repo.py` — ereditano da `BaseRepo`
- `fdp_app/pathtracks/routes.py` — supporta `?on_behalf_of=<id>` in `new` e `create`. Sostituisce O(n*m) check in `download_doc` con `find_owner_employee_for_doc`. Admin override per `submit` (parametro `force=True` dietro check ruolo)
- `fdp_app/coordinates/routes.py` — supporta `?on_behalf_of=<id>`
- `fdp_app/templates/dashboard/index.html` — card "Amministrazione" attivata (link a `/admin/representable`)
- `fdp_app/templates/base.html` — navbar: aggiunge link "Admin" se l'utente può rappresentare almeno un collega
- `config/settings.py` — aggiunge `MAX_CONTENT_LENGTH = UPLOAD_MAX_FILES_PER_PATHTRACK * UPLOAD_MAX_BYTES`
- `fdp_app/auth/decorators.py` — nuovo decoratore `@admin_required` (verifica FC>60 e esistenza rappresentati)

---

## Task

### Fase A — Pre-fix Piano 3 review

#### Task 1: `BaseRepo` + DRY su `_open_cursor`

**Files:**
- Create: `fdp_app/repos/base_repo.py`
- Modify: `fdp_app/repos/employee_repo.py`, `coordinate_repo.py`, `pathtrack_repo.py`, `doc_repo.py`, `rate_repo.py`, `registry_repo.py`

Step 1: Create `fdp_app/repos/base_repo.py`:

```python
"""Base class for repositories: shared cursor management."""
from __future__ import annotations

from flask import has_app_context


class BaseRepo:
    """Provides `_open_cursor()` that uses flask.g in production
    and falls back to self._db.cursor() in unit tests."""

    def __init__(self, db) -> None:
        self._db = db

    def _open_cursor(self):
        if has_app_context():
            from fdp_app.db import get_request_db
            return get_request_db().cursor()
        return self._db.cursor()
```

Step 2: In each of the 6 existing repos:
- Add `from fdp_app.repos.base_repo import BaseRepo` import
- Change class declaration: `class EmployeeRepo(BaseRepo):` (and similar)
- Remove the local `__init__` if it only stores `self._db = db` (now inherited)
- Remove the local `_open_cursor` method (now inherited)

Step 3: Run all tests, expect 148 passed.

Commit: `refactor(repos): extract BaseRepo with shared _open_cursor`

---

#### Task 2: `MAX_CONTENT_LENGTH` Flask-level

**File:** `config/settings.py`

Add to `Settings` class:

```python
MAX_CONTENT_LENGTH: int = (
    UPLOAD_MAX_BYTES * (UPLOAD_MAX_FILES_PER_PATHTRACK + 1)
)  # +1 for the sheet PDF
```

(Definito DOPO `UPLOAD_MAX_BYTES` e `UPLOAD_MAX_FILES_PER_PATHTRACK`. Flask automaticamente legge `MAX_CONTENT_LENGTH` da config e rifiuta richieste più grandi con 413.)

No new tests required (Flask behavior).

Commit: `feat(config): set MAX_CONTENT_LENGTH to prevent memory exhaustion`

---

#### Task 3: SQL JOIN per `download_doc` ownership check

**Files:**
- Modify: `fdp_app/repos/doc_repo.py` (add `find_owner_employee_for_doc`)
- Modify: `fdp_app/pathtracks/routes.py` (use new method, drop O(n*m) loop)
- Modify: `tests/test_doc_repo.py` (add tests for new method)

Step 1: Add to `doc_repo.py`:

```python
_QUERY_FIND_OWNER = """
SELECT pt.EmployeeHireHistoryId, COALESCE(pt.InBehalfOfId, pt.EmployeeHireHistoryId) AS BeneficiaryId
FROM Employee.fdp.PathTrackDocs d
JOIN Employee.fdp.PathTracks pt ON pt.PathTrackId = d.PathTrackId
WHERE d.PathTrackDocId = ?
  AND d.DateOut IS NULL
  AND pt.DateOut IS NULL
"""


# Method on PathTrackDocRepo:
def find_owner_employee_for_doc(self, *, doc_id: int):
    """Returns (employee_hire_history_id, beneficiary_id) tuple, or None."""
    cursor = self._open_cursor()
    try:
        cursor.execute(_QUERY_FIND_OWNER, doc_id)
        row = cursor.fetchone()
    finally:
        cursor.close()
    if row is None:
        return None
    return (int(row[0]), int(row[1]))
```

Step 2: In `pathtracks/routes.py`, replace the body of `download_doc` ownership check with:

```python
@bp.route("/docs/<int:doc_id>/download", methods=["GET"])
@login_required
def download_doc(doc_id: int):
    doc_repo = PathTrackDocRepo(current_app.config["_db"])
    try:
        pdf_bytes, title = doc_repo.get_blob(doc_id=doc_id)
    except FileNotFoundError:
        abort(404)

    # Ownership check via SQL JOIN
    owner = doc_repo.find_owner_employee_for_doc(doc_id=doc_id)
    if owner is None:
        abort(404)
    employee_id, beneficiary_id = owner
    if session["user_id"] not in (employee_id, beneficiary_id):
        abort(404)

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{title}.pdf"'},
    )
```

Step 3: Add tests in `test_doc_repo.py`:

```python
def test_find_owner_employee_for_doc_returns_owner():
    db, cursor = _make_db(fetchone=(10, 10))
    repo = PathTrackDocRepo(db)
    result = repo.find_owner_employee_for_doc(doc_id=42)
    assert result == (10, 10)


def test_find_owner_employee_for_doc_returns_beneficiary_when_in_behalf():
    db, cursor = _make_db(fetchone=(10, 25))  # inserito da 10 per conto di 25
    repo = PathTrackDocRepo(db)
    result = repo.find_owner_employee_for_doc(doc_id=42)
    assert result == (10, 25)


def test_find_owner_employee_for_doc_returns_none_when_missing():
    db, _ = _make_db(fetchone=None)
    repo = PathTrackDocRepo(db)
    assert repo.find_owner_employee_for_doc(doc_id=999) is None
```

Step 4: Run all tests + commit.

Commit: `refactor(pathtracks): SQL JOIN for download_doc ownership check`

---

### Fase B — Representable + admin scaffolding

#### Task 4: `EmployeeRepo.find_representable_for`

**Files:**
- Modify: `fdp_app/repos/employee_repo.py`
- Test: `tests/test_employee_repo.py` (extend) or new `tests/test_employee_repo_representable.py`

Step 1: Add to `employee_repo.py`:

```python
_QUERY_REPRESENTABLE = """
SELECT
    h.EmployeeHireHistoryId,
    e.EmployeeSurname,
    e.EmployeeName,
    s.SubCdcId,
    f.FunctionCode
FROM Employee.dbo.Employees e
JOIN Employee.dbo.EmployeeHireHistory h
     ON h.EmployeeId = e.EmployeeId
    AND h.EndWorkDate IS NULL
    AND h.EmployeerId = 2
JOIN Employee.dbo.EmployeeCdcStories s
     ON s.EmployeeHireHistoryId = h.EmployeeHireHistoryId
    AND s.DateOut IS NULL
JOIN Employee.dbo.Functions f
     ON f.FunctionId = s.FunctionId
WHERE s.SubCdcId = ?
  AND f.FunctionCode < ?
ORDER BY e.EmployeeSurname, e.EmployeeName
"""


@dataclass(frozen=True)
class RepresentableEmployee:
    employee_hire_history_id: int
    surname: str
    name: str
    sub_cdc_id: int
    function_code: int

    @property
    def full_name(self) -> str:
        return f"{self.surname} {self.name}"


# Add to EmployeeRepo class:
def find_representable_for(self, *, sub_cdc_id: int, min_function_code: int = 60) -> list[RepresentableEmployee]:
    """Lists employees that the logged-in user (FC > min) can represent.
    These are employees with same SubCdcId AND FunctionCode < min_function_code."""
    cursor = self._open_cursor()
    try:
        cursor.execute(_QUERY_REPRESENTABLE, sub_cdc_id, min_function_code)
        rows = cursor.fetchall()
    finally:
        cursor.close()
    return [
        RepresentableEmployee(
            employee_hire_history_id=r[0],
            surname=r[1],
            name=r[2],
            sub_cdc_id=r[3],
            function_code=r[4],
        )
        for r in rows
    ]
```

Step 2: Tests for the new method.

Step 3: Run tests + commit.

Commit: `feat(repos): EmployeeRepo.find_representable_for`

---

#### Task 5: `@admin_required` decorator

**Files:**
- Modify: `fdp_app/auth/decorators.py`
- Test: `tests/test_auth_decorators.py` (extend)

Step 1: Add decorator:

```python
def admin_required(view: Callable) -> Callable:
    """Verifica che l'utente abbia FunctionCode > 60.
    Sennò 403."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        fc = session.get("function_code")
        if fc is None or fc <= 60:
            from flask import abort
            abort(403)
        return view(*args, **kwargs)

    return wrapper
```

Step 2: Tests for admin_required (3 cases: anonymous redirect, FC<=60 → 403, FC>60 → view called).

Step 3: Commit.

Commit: `feat(auth): admin_required decorator`

---

#### Task 6: Blueprint `/admin/representable`

**Files:**
- Create: `fdp_app/admin/__init__.py` (empty)
- Create: `fdp_app/admin/routes.py`
- Create: `fdp_app/templates/admin/representable.html`
- Modify: `fdp_app/__init__.py` — register admin blueprint
- Modify: `fdp_app/templates/dashboard/index.html` — link card admin
- Test: `tests/test_admin_routes.py`

Step 1: `fdp_app/admin/routes.py`:

```python
"""Route amministrative (rappresentanza colleghi + storico + export)."""
from __future__ import annotations

from flask import (
    Blueprint, current_app, render_template, request, session,
)

from fdp_app.auth.decorators import admin_required, login_required
from fdp_app.repos.employee_repo import EmployeeRepo

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/representable", methods=["GET"])
@login_required
@admin_required
def representable():
    db = current_app.config["_db"]
    employee_repo = EmployeeRepo(db)
    employees = employee_repo.find_representable_for(
        sub_cdc_id=session["sub_cdc_id"],
        min_function_code=current_app.config["_settings_cls"].MIN_FUNCTION_CODE_FOR_LOGIN,
    )
    return render_template(
        "admin/representable.html",
        employees=employees,
    )
```

Step 2: `fdp_app/templates/admin/representable.html`:

```html
{% extends "base.html" %}
{% block title %}Rappresentati - Fogli di Percorso{% endblock %}
{% block content %}
<h2><i class="bi bi-people-fill"></i> Dipendenti rappresentabili</h2>
<p class="text-muted">
    Puoi inserire dichiarazioni e gestire punti di partenza per conto dei colleghi
    elencati qui sotto (stesso SubCdc, FunctionCode &lt; {{ session.function_code or 60 }}).
</p>

{% if employees %}
<table class="table table-striped">
    <thead>
        <tr>
            <th>Cognome Nome</th>
            <th>FC</th>
            <th>Azioni</th>
        </tr>
    </thead>
    <tbody>
        {% for emp in employees %}
        <tr>
            <td>{{ emp.full_name }}</td>
            <td>{{ emp.function_code }}</td>
            <td>
                <a class="btn btn-sm btn-outline-primary"
                   href="{{ url_for('coordinates.index') }}?on_behalf_of={{ emp.employee_hire_history_id }}">
                    <i class="bi bi-geo-alt"></i> Mappa
                </a>
                <a class="btn btn-sm btn-outline-primary"
                   href="{{ url_for('pathtracks.new') }}?on_behalf_of={{ emp.employee_hire_history_id }}">
                    <i class="bi bi-receipt"></i> Nuova dichiarazione
                </a>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% else %}
<div class="alert alert-info">
    Nessun collega rappresentabile per il tuo SubCdc.
</div>
{% endif %}

<a href="{{ url_for('admin.history') }}" class="btn btn-link mt-3">
    <i class="bi bi-clock-history"></i> Vedi storico dichiarazioni del SubCdc
</a>
{% endblock %}
```

Step 3: Register blueprint in `fdp_app/__init__.py`:

```python
    from fdp_app.admin.routes import bp as admin_bp
    app.register_blueprint(admin_bp)
```

Step 4: Activate dashboard card (modify `templates/dashboard/index.html`): replace the disabled "Amministrazione" link with:

```html
<a class="btn btn-outline-primary" href="{{ url_for('admin.representable') }}">
    Vai all'area admin <i class="bi bi-arrow-right"></i>
</a>
```

Step 5: Tests for `/admin/representable` (4 cases: anonymous redirect, FC<=60 → 403, FC>60 lists, empty list).

Note: `history` endpoint will be created in Task 8. To avoid `BuildError` in the template, add a stub:

```python
@bp.route("/history", methods=["GET"], endpoint="history")
@login_required
@admin_required
def _history_stub():
    return "history - not yet implemented", 501
```

Step 6: Run tests + commit.

Commit: `feat(admin): /admin/representable list of colleagues to represent`

---

### Fase C — InBehalfOf flow

#### Task 7: Coordinates + pathtracks accept `?on_behalf_of=<id>`

**Files:**
- Modify: `fdp_app/coordinates/routes.py`
- Modify: `fdp_app/coordinates/service.py` (in realtà già supporta `target_employee_id` implicito)
- Modify: `fdp_app/pathtracks/routes.py`
- Test: extend `tests/test_coordinates_routes.py` and `tests/test_pathtracks_routes.py`

Step 1: Helper function in a shared location (could go in `fdp_app/auth/helpers.py`, but for simplicity inline in routes):

```python
# In coordinates/routes.py and pathtracks/routes.py, add at module level:
def _resolve_target_employee(default_employee_id: int) -> tuple[int, int | None]:
    """Returns (target_employee_id, in_behalf_of_id).
    If ?on_behalf_of=<id> is present and valid, target is the represented employee.
    Otherwise target is the logged-in user.

    Raises 403 if the requested representation is not allowed
    (FC>60, same SubCdcId, target FC<60).
    """
    raw = request.args.get("on_behalf_of") or request.form.get("on_behalf_of")
    if not raw:
        return default_employee_id, None
    try:
        target_id = int(raw)
    except ValueError:
        abort(400)

    if target_id == default_employee_id:
        return default_employee_id, None

    # Verify the logged-in user CAN represent target_id
    db = current_app.config["_db"]
    employee_repo = EmployeeRepo(db)
    representables = employee_repo.find_representable_for(
        sub_cdc_id=session["sub_cdc_id"],
        min_function_code=current_app.config["_settings_cls"].MIN_FUNCTION_CODE_FOR_LOGIN,
    )
    if not any(r.employee_hire_history_id == target_id for r in representables):
        abort(403)

    return target_id, target_id
```

Step 2: In `coordinates/routes.py`:
- `index()`: call `_resolve_target_employee(session["user_id"])` to determine which coordinate to read. Pass `target_id` to `find_active` instead of `session["user_id"]`. Pass also to template for use in form (hidden field).
- `create()`: call `_resolve_target_employee`, then call service.create with `employee_hire_history_id=target_id` (the coordinate is for the target).
- `delete()`: same.

Note: `PathTrackCoordinates.EmployeerHireHistoryId` holds the EMPLOYEE the point belongs to (the represented one if delegated). So this is consistent.

Step 3: In `pathtracks/routes.py`:
- `new()`: resolve target. If different, pass `in_behalf_of=target_id` and `target_employee_for_coord=target_id`. Show banner "Dichiarazione per <Nome Cognome>".
- `create()`: pass `in_behalf_of_id=in_behalf_of` to `service.create_draft_*`.

Step 4: Update templates `coordinates/index.html` and `pathtracks/new.html` to:
- Show a banner with the represented employee's name when `on_behalf_of` is active
- Add a hidden `<input name="on_behalf_of" value="...">` in forms so the param survives POST

Step 5: Tests.

Step 6: Commit.

Commit: `feat(admin): support ?on_behalf_of= for coordinates and pathtracks`

---

### Fase D — History admin

#### Task 8: `PathTrackRepo.list_for_sub_cdc` + admin history route

**Files:**
- Modify: `fdp_app/repos/pathtrack_repo.py` — new method `list_for_sub_cdc`
- Modify: `fdp_app/admin/routes.py` — `history()` route
- Create: `fdp_app/templates/admin/history.html`
- Test: extend `tests/test_pathtrack_repo.py` (new method) and `tests/test_admin_routes.py`

Step 1: New query + method in `pathtrack_repo.py`:

```python
_QUERY_LIST_SUB_CDC = """
SELECT
    pt.PathTrackId, pt.RegistryId, pt.DatePathTrack, pt.DeclaratedPathId,
    pt.InBehalfOfId, pt.ReimbursementType, pt.NumberOfTrips, pt.RoadKm,
    pt.RateIdUsed, pt.TaxiTotalEur, pt.ComputedAmountEur, pt.Status, pt.SubmittedOn,
    e.EmployeeSurname, e.EmployeeName
FROM Employee.fdp.PathTracks pt
JOIN Employee.dbo.EmployeeHireHistory h
     ON h.EmployeeHireHistoryId = COALESCE(pt.InBehalfOfId, pt.EmployeeHireHistoryId)
JOIN Employee.dbo.Employees e ON e.EmployeeId = h.EmployeeId
JOIN Employee.dbo.EmployeeCdcStories s
     ON s.EmployeeHireHistoryId = h.EmployeeHireHistoryId
    AND s.DateOut IS NULL
WHERE s.SubCdcId = ?
  AND pt.DateOut IS NULL
  /*FILTERS*/
ORDER BY pt.DatePathTrack DESC, e.EmployeeSurname, e.EmployeeName
"""


@dataclass(frozen=True)
class PathTrackWithEmployee:
    row: "PathTrackRow"
    employee_surname: str
    employee_name: str

    @property
    def employee_full_name(self) -> str:
        return f"{self.employee_surname} {self.employee_name}"


def list_for_sub_cdc(self, *, sub_cdc_id: int, year: int | None = None,
                     month: int | None = None,
                     reimbursement_type: str | None = None) -> list[PathTrackWithEmployee]:
    filters = []
    params: list = [sub_cdc_id]
    if year is not None:
        filters.append("YEAR(pt.DatePathTrack) = ?")
        params.append(year)
    if month is not None:
        filters.append("MONTH(pt.DatePathTrack) = ?")
        params.append(month)
    if reimbursement_type:
        filters.append("pt.ReimbursementType = ?")
        params.append(reimbursement_type)
    sql = _QUERY_LIST_SUB_CDC.replace(
        "/*FILTERS*/",
        ("AND " + " AND ".join(filters)) if filters else "",
    )
    cursor = self._open_cursor()
    try:
        cursor.execute(sql, *params)
        rows = cursor.fetchall()
    finally:
        cursor.close()
    return [
        PathTrackWithEmployee(
            row=PathTrackRow(
                # same as _row_to_obj but stop at col 12 (Status), 13 (SubmittedOn)
                path_track_id=r[0], registry_id=r[1], date_path_track=r[2],
                declarated_path_id=r[3], in_behalf_of_id=r[4],
                reimbursement_type=r[5].rstrip() if isinstance(r[5], str) else r[5],
                number_of_trips=r[6], road_km=float(r[7]), rate_id_used=r[8],
                taxi_total_eur=float(r[9]) if r[9] is not None else None,
                computed_amount_eur=float(r[10]),
                status=r[11].rstrip() if isinstance(r[11], str) else r[11],
                submitted_on=r[12],
            ),
            employee_surname=r[13],
            employee_name=r[14],
        )
        for r in rows
    ]
```

Step 2: Replace the stub `_history_stub` in `admin/routes.py` with:

```python
@bp.route("/history", methods=["GET"])
@login_required
@admin_required
def history():
    db = current_app.config["_db"]
    pathtrack_repo = PathTrackRepo(db)
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    reimbursement_type = request.args.get("type") or None
    if reimbursement_type:
        reimbursement_type = reimbursement_type.upper()
    rows = pathtrack_repo.list_for_sub_cdc(
        sub_cdc_id=session["sub_cdc_id"],
        year=year,
        month=month,
        reimbursement_type=reimbursement_type,
    )
    return render_template(
        "admin/history.html",
        rows=rows,
        year=year, month=month, type=reimbursement_type,
        month_names=_MONTH_NAMES_IT,
    )
```

(import `PathTrackRepo` and `_MONTH_NAMES_IT` at top.)

Step 3: Template `admin/history.html`:

```html
{% extends "base.html" %}
{% block title %}Storico SubCdc - Fogli di Percorso{% endblock %}
{% block content %}
<h2><i class="bi bi-clock-history"></i> Storico dichiarazioni SubCdc</h2>

<form method="get" class="row g-2 mb-3">
    <div class="col-md-2">
        <label class="form-label">Anno</label>
        <input type="number" name="year" min="2024" max="2100"
               value="{{ year or '' }}" class="form-control">
    </div>
    <div class="col-md-2">
        <label class="form-label">Mese</label>
        <select name="month" class="form-select">
            <option value="">Tutti</option>
            {% for m in range(1, 13) %}
            <option value="{{ m }}" {% if month == m %}selected{% endif %}>
                {{ month_names[m] }}
            </option>
            {% endfor %}
        </select>
    </div>
    <div class="col-md-2">
        <label class="form-label">Tipo</label>
        <select name="type" class="form-select">
            <option value="">Tutti</option>
            <option value="CARBURANTE" {% if type == "CARBURANTE" %}selected{% endif %}>Carburante</option>
            <option value="TAXI" {% if type == "TAXI" %}selected{% endif %}>Taxi</option>
        </select>
    </div>
    <div class="col-md-2 d-flex align-items-end">
        <button type="submit" class="btn btn-primary"><i class="bi bi-search"></i> Filtra</button>
    </div>
    <div class="col-md-4 d-flex align-items-end justify-content-end">
        {% if year and month %}
        <a class="btn btn-outline-success"
           href="{{ url_for('admin.export', year=year, month=month) }}">
            <i class="bi bi-file-earmark-excel"></i> Export XLSX
        </a>
        {% endif %}
    </div>
</form>

{% if rows %}
<table class="table table-striped">
    <thead>
        <tr>
            <th>Dipendente</th>
            <th>Mese</th>
            <th>Stato</th>
            <th>Tipo</th>
            <th>Viaggi</th>
            <th>Importo</th>
            <th>Reg.</th>
            <th></th>
        </tr>
    </thead>
    <tbody>
        {% for entry in rows %}
        <tr>
            <td>{{ entry.employee_full_name }}</td>
            <td>{{ month_names[entry.row.date_path_track.month] }} {{ entry.row.date_path_track.year }}</td>
            <td>
                {% if entry.row.status == "DRAFT" %}
                <span class="badge bg-warning text-dark">BOZZA</span>
                {% else %}
                <span class="badge bg-success">INVIATA</span>
                {% endif %}
            </td>
            <td>{{ entry.row.reimbursement_type }}</td>
            <td>{{ entry.row.number_of_trips }}</td>
            <td>€ {{ "%.2f"|format(entry.row.computed_amount_eur) }}</td>
            <td>{{ entry.row.registry_id or "-" }}</td>
            <td>
                <a class="btn btn-sm btn-outline-primary"
                   href="{{ url_for('pathtracks.view', path_track_id=entry.row.path_track_id) }}">
                    Dettagli
                </a>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% else %}
<div class="alert alert-info">Nessuna dichiarazione trovata con i filtri selezionati.</div>
{% endif %}
{% endblock %}
```

Step 4: Tests.

Step 5: Commit.

Commit: `feat(admin): /admin/history with filters by year/month/type`

---

### Fase E — Export XLSX

#### Task 9: Export XLSX endpoint

**Files:**
- Modify: `fdp_app/admin/routes.py` — `export()` route
- Modify: `fdp_app/admin/service.py` — `build_xlsx(rows) -> bytes`
- Test: `tests/test_admin_export.py`

Step 1: `fdp_app/admin/service.py`:

```python
"""Helpers admin: generazione XLSX."""
from __future__ import annotations

from io import BytesIO
from typing import Iterable

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill


def build_xlsx(rows, *, year: int, month: int, month_name: str) -> bytes:
    """Genera un XLSX in memoria con una riga per ciascun PathTrackWithEmployee."""
    wb = Workbook()
    ws = wb.active
    ws.title = f"{month_name} {year}"

    headers = [
        "Cognome", "Nome", "Tipo", "Stato", "N. Viaggi A/R", "Km one-way",
        "Importo (€)", "N. Registro", "Data invio",
    ]
    ws.append(headers)
    # Style header
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="0b2a5b")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill

    for entry in rows:
        ws.append([
            entry.employee_surname,
            entry.employee_name,
            entry.row.reimbursement_type,
            entry.row.status,
            entry.row.number_of_trips,
            entry.row.road_km,
            entry.row.computed_amount_eur,
            entry.row.registry_id or "",
            entry.row.submitted_on.strftime("%d/%m/%Y %H:%M") if entry.row.submitted_on else "",
        ])

    # Auto-width approssimativo (max 50 chars)
    for col in ws.columns:
        length = max(len(str(c.value or "")) for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(length + 2, 50)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
```

Step 2: Add to `admin/routes.py`:

```python
from datetime import date as Date
from flask import Response, abort

from fdp_app.admin.service import build_xlsx
from fdp_app.repos.pathtrack_repo import PathTrackRepo


@bp.route("/export", methods=["GET"])
@login_required
@admin_required
def export():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    if not year or not month or not (1 <= month <= 12):
        abort(400)
    db = current_app.config["_db"]
    pathtrack_repo = PathTrackRepo(db)
    rows = pathtrack_repo.list_for_sub_cdc(
        sub_cdc_id=session["sub_cdc_id"],
        year=year,
        month=month,
    )
    xlsx_bytes = build_xlsx(
        rows, year=year, month=month, month_name=_MONTH_NAMES_IT[month],
    )
    filename = f"fogli-di-percorso-{year:04d}-{month:02d}.xlsx"
    return Response(
        xlsx_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

Step 3: Tests:
- `test_build_xlsx_generates_workbook` (verify with openpyxl re-open)
- `test_export_endpoint_requires_admin`
- `test_export_endpoint_returns_xlsx_with_correct_filename`
- `test_export_endpoint_rejects_invalid_month`

Step 4: Commit.

Commit: `feat(admin): /admin/export monthly XLSX download`

---

### Fase F — Admin submit override

#### Task 10: Admin può inviare bozza fuori finestra

**Files:**
- Modify: `fdp_app/pathtracks/service.py` — `submit` accept `force: bool = False`
- Modify: `fdp_app/pathtracks/routes.py` — `submit` route accept `force` param if user is admin
- Modify: `fdp_app/templates/pathtracks/view.html` — show "Conferma e invia (override admin)" button for FC>60 even outside window
- Test: extend service + route tests

Step 1: In `service.py`, modify `submit`:

```python
def submit(
    self,
    *,
    path_track_id: int,
    employee_hire_history_id: int,
    full_name: str,
    force: bool = False,
) -> int:
    row = self._pathtrack_repo.find_by_id(
        path_track_id=path_track_id,
        employee_hire_history_id=employee_hire_history_id,
    )
    if row is None:
        raise NotADraftError("Dichiarazione non trovata o non posseduta")
    if row.status != "DRAFT":
        raise NotADraftError("Dichiarazione gia' inviata o cancellata")
    if not force and not can_submit_for(row.date_path_track):
        raise DeadlineClosedError(
            f"Finestra di invio chiusa per {row.date_path_track:%Y-%m}"
        )
    # ... rest unchanged
```

Step 2: In `routes.py` `submit` view:

```python
@bp.route("/<int:path_track_id>/submit", methods=["POST"])
@login_required
def submit(path_track_id: int):
    force = (request.form.get("force") == "1" and session.get("function_code", 0) > 60)
    service = _build_service()
    try:
        registry_id = service.submit(
            path_track_id=path_track_id,
            employee_hire_history_id=session["user_id"],
            full_name=session["full_name"],
            force=force,
        )
        # ...
```

Step 3: In `view.html`, near the existing submit button, add an admin-only override:

```html
{% if not can_submit and row.status == "DRAFT" and session.function_code > 60 %}
<form method="post" action="{{ url_for('pathtracks.submit', path_track_id=row.path_track_id) }}"
      class="d-inline">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <input type="hidden" name="force" value="1">
    <button type="submit" class="btn btn-warning"
            onclick="return confirm('Invio admin (override scadenza). Confermi?');">
        <i class="bi bi-shield-check"></i> Invia (override admin)
    </button>
</form>
{% endif %}
```

Step 4: Tests.

Step 5: Commit.

Commit: `feat(pathtracks): admin can force-submit drafts past the deadline`

---

### Fase G — Smoke test + tag

#### Task 11: Smoke test + tag `v0.4.0-admin`

1. Eseguire tutti i test:
   ```bash
   .venv\Scripts\python.exe -m pytest -v
   ```
   Expected: tutti verdi (target ~175 test).

2. Smoke test manuale:
   - Login → dashboard → click "Vai all'area admin" → vede lista rappresentati
   - Click "Mappa" su un rappresentato → /coordinates?on_behalf_of=<id> → banner "Per <Nome>" → crea punto
   - Click "Nuova dichiarazione" su un rappresentato → /pathtracks/new?on_behalf_of=<id> → compila → salva bozza
   - Verifica DB: PathTracks ha InBehalfOfId valorizzato
   - Click "Storico" → vede tutte le dichiarazioni del SubCdc → applica filtri → click Export XLSX → scarica
   - Apri XLSX in Excel → verifica colonne e dati corretti
   - Submit override admin: bozza scaduta + bottone giallo → invia → RegistryId assegnato

3. Tag:
   ```bash
   git tag -a v0.4.0-admin -m "Piano 4 - Admin completato"
   git push origin main
   git push origin v0.4.0-admin
   ```

---

## Definition of Done

- [x] BaseRepo + DRY refactor
- [x] MAX_CONTENT_LENGTH set
- [x] download_doc usa SQL JOIN
- [x] EmployeeRepo.find_representable_for + RepresentableEmployee
- [x] @admin_required decoratore
- [x] /admin/representable
- [x] /coordinates e /pathtracks supportano ?on_behalf_of
- [x] /admin/history con filtri
- [x] /admin/export XLSX
- [x] Admin submit override
- [x] Tutti i test verdi
- [x] Tag v0.4.0-admin

## Prossimo piano

- **Piano 5 — Notifiche & scheduler** (CLI send-reminders, close-month, Windows Task Scheduler runbook)
