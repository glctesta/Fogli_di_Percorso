# Admin km-rates management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `/admin/fuel-rates` page (GET list + POST insert) that lets admins create new versions of `PathTrackReimbursementRates` (avg consumption km/L + avg fuel price EUR/L), mirroring the existing `/admin/bnr-rates` pattern.

**Architecture:** Extend the existing `RateRepo` with `insert` and `list_recent` methods (and three optional audit fields on the `Rate` dataclass). Add two new route handlers in `fdp_app/admin/routes.py` that delegate to the repo, validate input, and catch `pyodbc.IntegrityError` for the `UNIQUE(ValidFrom)` constraint. Add a Jinja template that mirrors `bnr_rates.html` and a nav link from `representable.html`. Insert-only versioning — no edit/delete. Spec: [docs/superpowers/specs/2026-05-25-admin-km-rates-design.md](../specs/2026-05-25-admin-km-rates-design.md).

**Tech Stack:** Python 3.11+, Flask, pyodbc (SQL Server), pytest, Jinja2, Flask-Babel, Bootstrap 5.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `fdp_app/repos/rate_repo.py` | Repo for `PathTrackReimbursementRates`. Adds `insert` + `list_recent` and extends `Rate` with audit fields. | Modify |
| `fdp_app/admin/routes.py` | Admin route handlers. Adds GET/POST `/admin/fuel-rates`. | Modify |
| `fdp_app/templates/admin/fuel_rates.html` | Page template: form + history table. | Create |
| `fdp_app/templates/admin/representable.html` | Adds nav link to the new page. | Modify |
| `tests/test_rate_repo.py` | Existing repo tests. Adds tests for `insert` and `list_recent`. | Modify |
| `tests/test_admin_fuel_rates.py` | New route-level tests, modelled on `test_admin_bnr_rates.py`. | Create |

Tasks are sequenced bottom-up so each layer is green before the next builds on it: repo → route → template → nav.

---

## Task 1: Extend `Rate` dataclass with audit fields

**Files:**
- Modify: `fdp_app/repos/rate_repo.py` (the `Rate` dataclass, lines ~20-25)
- Test: `tests/test_rate_repo.py`

Add three optional fields (`valid_from`, `valid_to`, `user_sys`) with defaults so existing `find_for_date` construction keeps working untouched. The new fields are only populated by `list_recent` (next task).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_rate_repo.py`:

```python
def test_rate_dataclass_audit_fields_default_to_none_or_empty():
    r = Rate(rate_id=1, avg_consumption_km_l=15.0, avg_fuel_price_eur_l=1.7)
    assert r.valid_from is None
    assert r.valid_to is None
    assert r.user_sys == ""


def test_rate_dataclass_accepts_audit_fields():
    r = Rate(
        rate_id=1, avg_consumption_km_l=15.0, avg_fuel_price_eur_l=1.7,
        valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31),
        user_sys="admin",
    )
    assert r.valid_from == date(2026, 1, 1)
    assert r.valid_to == date(2026, 12, 31)
    assert r.user_sys == "admin"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rate_repo.py::test_rate_dataclass_audit_fields_default_to_none_or_empty -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument` or similar.

- [ ] **Step 3: Modify the dataclass**

In `fdp_app/repos/rate_repo.py`, change the import line and the `Rate` dataclass:

```python
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from fdp_app.repos.base_repo import BaseRepo


@dataclass(frozen=True)
class Rate:
    rate_id: int
    avg_consumption_km_l: float
    avg_fuel_price_eur_l: float
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    user_sys: str = ""
```

(`List` will be used by the next task; importing now avoids touching the import block twice.)

- [ ] **Step 4: Run both new tests and the existing tests to verify no regression**

Run: `python -m pytest tests/test_rate_repo.py -v`
Expected: all tests PASS, including the three existing `test_find_for_date_*` tests and the two new dataclass tests.

- [ ] **Step 5: Commit**

```bash
git add fdp_app/repos/rate_repo.py tests/test_rate_repo.py
git commit -m "feat(repos): extend Rate dataclass with optional audit fields"
```

---

## Task 2: Add `RateRepo.insert`

**Files:**
- Modify: `fdp_app/repos/rate_repo.py`
- Test: `tests/test_rate_repo.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_rate_repo.py`:

```python
def test_insert_executes_with_keyword_args_and_returns_id():
    db, cursor = _make_db(fetchone=(42,))
    repo = RateRepo(db)

    new_id = repo.insert(
        avg_consumption_km_l=15.0,
        avg_fuel_price_eur_l=1.700,
        valid_from=date(2026, 6, 1),
        valid_to=date(2026, 12, 31),
        user_sys="Rossi Mario",
    )

    assert new_id == 42
    sql_text, *params = cursor.execute.call_args[0]
    assert "INSERT INTO" in sql_text
    assert "PathTrackReimbursementRates" in sql_text
    assert "OUTPUT INSERTED.RateId" in sql_text
    assert params == [15.0, 1.700, date(2026, 6, 1), date(2026, 12, 31), "Rossi Mario"]
    cursor.close.assert_called_once()


def test_insert_accepts_null_valid_to():
    db, cursor = _make_db(fetchone=(43,))
    repo = RateRepo(db)

    new_id = repo.insert(
        avg_consumption_km_l=15.0,
        avg_fuel_price_eur_l=1.700,
        valid_from=date(2026, 6, 1),
        valid_to=None,
        user_sys="admin",
    )

    assert new_id == 43
    _, *params = cursor.execute.call_args[0]
    assert params[3] is None
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python -m pytest tests/test_rate_repo.py::test_insert_executes_with_keyword_args_and_returns_id tests/test_rate_repo.py::test_insert_accepts_null_valid_to -v`
Expected: FAIL — `AttributeError: 'RateRepo' object has no attribute 'insert'`.

- [ ] **Step 3: Add the SQL constant and the `insert` method**

In `fdp_app/repos/rate_repo.py`, add this module-level constant near `_QUERY`:

```python
_QUERY_INSERT = """
INSERT INTO Employee.fdp.PathTrackReimbursementRates
    (AvgConsumptionKmL, AvgFuelPriceEurL, ValidFrom, ValidTo, UserSys)
OUTPUT INSERTED.RateId
VALUES (?, ?, ?, ?, ?)
"""
```

Then add this method to `RateRepo` (after `find_for_date`):

```python
def insert(self, *, avg_consumption_km_l: float, avg_fuel_price_eur_l: float,
           valid_from: date, valid_to: Optional[date], user_sys: str) -> int:
    cursor = self._open_cursor()
    try:
        cursor.execute(
            _QUERY_INSERT,
            avg_consumption_km_l, avg_fuel_price_eur_l,
            valid_from, valid_to, user_sys,
        )
        row = cursor.fetchone()
        return int(row[0])
    finally:
        cursor.close()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_rate_repo.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add fdp_app/repos/rate_repo.py tests/test_rate_repo.py
git commit -m "feat(repos): RateRepo.insert for new km-rate versions"
```

---

## Task 3: Add `RateRepo.list_recent`

**Files:**
- Modify: `fdp_app/repos/rate_repo.py`
- Test: `tests/test_rate_repo.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_rate_repo.py`:

```python
def test_list_recent_returns_rate_objects_with_audit_fields():
    db = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        (7, 15.0, 1.700, date(2026, 6, 1), date(2026, 12, 31), "admin"),
        (6, 14.0, 1.650, date(2026, 1, 1), None, "Rossi"),
    ]
    db.cursor.return_value = cursor
    repo = RateRepo(db)

    rows = repo.list_recent(limit=20)

    assert len(rows) == 2
    assert rows[0] == Rate(
        rate_id=7, avg_consumption_km_l=15.0, avg_fuel_price_eur_l=1.700,
        valid_from=date(2026, 6, 1), valid_to=date(2026, 12, 31), user_sys="admin",
    )
    assert rows[1].valid_to is None
    sql_text, *params = cursor.execute.call_args[0]
    assert "TOP (?)" in sql_text
    assert "ORDER BY ValidFrom DESC" in sql_text
    assert params == [20]
    cursor.close.assert_called_once()


def test_list_recent_returns_empty_list_when_no_rows():
    db = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    db.cursor.return_value = cursor
    repo = RateRepo(db)

    assert repo.list_recent(limit=10) == []
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python -m pytest tests/test_rate_repo.py::test_list_recent_returns_rate_objects_with_audit_fields tests/test_rate_repo.py::test_list_recent_returns_empty_list_when_no_rows -v`
Expected: FAIL — `AttributeError: 'RateRepo' object has no attribute 'list_recent'`.

- [ ] **Step 3: Add the SQL constant and the `list_recent` method**

In `fdp_app/repos/rate_repo.py`, add this module-level constant:

```python
_QUERY_LIST_RECENT = """
SELECT TOP (?) RateId, AvgConsumptionKmL, AvgFuelPriceEurL,
       ValidFrom, ValidTo, UserSys
FROM Employee.fdp.PathTrackReimbursementRates
ORDER BY ValidFrom DESC, RateId DESC
"""
```

Add this method to `RateRepo`:

```python
def list_recent(self, *, limit: int = 20) -> List[Rate]:
    cursor = self._open_cursor()
    try:
        cursor.execute(_QUERY_LIST_RECENT, limit)
        rows = cursor.fetchall()
    finally:
        cursor.close()
    return [
        Rate(
            rate_id=int(r[0]),
            avg_consumption_km_l=float(r[1]),
            avg_fuel_price_eur_l=float(r[2]),
            valid_from=r[3],
            valid_to=r[4],
            user_sys=r[5] if r[5] is not None else "",
        )
        for r in rows
    ]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_rate_repo.py -v`
Expected: all 7 tests in `tests/test_rate_repo.py` PASS.

- [ ] **Step 5: Commit**

```bash
git add fdp_app/repos/rate_repo.py tests/test_rate_repo.py
git commit -m "feat(repos): RateRepo.list_recent for admin history view"
```

---

## Task 4: Create empty `fuel_rates.html` template + GET route

**Files:**
- Modify: `fdp_app/admin/routes.py`
- Create: `fdp_app/templates/admin/fuel_rates.html`
- Create: `tests/test_admin_fuel_rates.py`

Implement the GET endpoint and a minimal template so the page renders. The form + table will go in the next task. This task ships a working GET that lists recent rates.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_admin_fuel_rates.py`:

```python
"""Test del /admin/fuel-rates CRUD."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_rate_repo():
    with patch("fdp_app.admin.routes.RateRepo") as cls:
        instance = MagicMock()
        instance.list_recent.return_value = []
        cls.return_value = instance
        yield instance


def _login_admin(client, eh_id=10, sub_cdc_id=42, fc=70):
    with client.session_transaction() as sess:
        sess["user_id"] = eh_id
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = sub_cdc_id
        sess["function_code"] = fc


def test_fuel_rates_requires_admin(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["function_code"] = 50
    response = client.get("/admin/fuel-rates")
    assert response.status_code == 403


def test_fuel_rates_empty_state(client, mock_rate_repo):
    _login_admin(client)
    response = client.get("/admin/fuel-rates")
    assert response.status_code == 200
    assert b"Nessuna tariffa" in response.data


def test_fuel_rates_lists_rates(client, mock_rate_repo):
    from fdp_app.repos.rate_repo import Rate
    _login_admin(client)
    mock_rate_repo.list_recent.return_value = [
        Rate(
            rate_id=7, avg_consumption_km_l=15.0, avg_fuel_price_eur_l=1.700,
            valid_from=date(2026, 6, 1), valid_to=None, user_sys="Rossi Mario",
        ),
    ]
    response = client.get("/admin/fuel-rates")
    assert response.status_code == 200
    assert b"15.00" in response.data
    assert b"1.700" in response.data
    assert b"2026-06-01" in response.data
    assert b"Rossi Mario" in response.data
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python -m pytest tests/test_admin_fuel_rates.py -v`
Expected: FAIL — `404 Not Found` (route doesn't exist yet) or `jinja2.exceptions.TemplateNotFound`.

- [ ] **Step 3: Add the import and the GET route**

In `fdp_app/admin/routes.py`, update the imports to include `RateRepo`:

```python
from fdp_app.repos.rate_repo import RateRepo
```

(Place it alphabetically with the other repo imports: it goes between `pathtrack_repo` and the existing ones.)

Then add this handler after `bnr_rates_create`:

```python
@bp.route("/fuel-rates", methods=["GET"])
@login_required
@admin_required
def fuel_rates():
    db = current_app.config["_db"]
    repo = RateRepo(db)
    recent = repo.list_recent(limit=20)
    return render_template(
        "admin/fuel_rates.html",
        recent=recent,
    )
```

- [ ] **Step 4: Create the template**

Create `fdp_app/templates/admin/fuel_rates.html`:

```jinja
{% extends "base.html" %}
{% block title %}{{ _('Tariffe rimborso km') }} - Fogli di Percorso{% endblock %}
{% block content %}
<h1 class="visually-hidden">{{ _('Gestione tariffe rimborso km') }}</h1>
<h2><i class="bi bi-fuel-pump"></i> {{ _('Tariffe rimborso km') }}</h2>

<p class="text-muted">
    {{ _('Gestisci consumo medio (km/L) e prezzo medio carburante (EUR/L). Ogni inserimento crea una nuova versione: i rimborsi gia\' registrati restano congelati sul RateId usato al momento del submit.') }}
</p>

<h4>{{ _('Tariffe attive e storiche') }}</h4>
{% if recent %}
<div class="table-responsive">
<table class="table table-striped">
    <thead>
        <tr>
            <th>{{ _('Consumo km/L') }}</th>
            <th>{{ _('Prezzo EUR/L') }}</th>
            <th>{{ _('€/km') }}</th>
            <th>{{ _('Valido da') }}</th>
            <th>{{ _('Valido fino a') }}</th>
            <th>{{ _('Inserito da') }}</th>
        </tr>
    </thead>
    <tbody>
        {% for r in recent %}
        <tr>
            <td>{{ "%.2f"|format(r.avg_consumption_km_l) }}</td>
            <td>{{ "%.3f"|format(r.avg_fuel_price_eur_l) }}</td>
            <td><strong>{{ "%.4f"|format(r.avg_fuel_price_eur_l / r.avg_consumption_km_l) }}</strong></td>
            <td>{{ r.valid_from.isoformat() if r.valid_from else '' }}</td>
            <td>{{ r.valid_to.isoformat() if r.valid_to else _('(aperto)') }}</td>
            <td>{{ r.user_sys }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>
</div>
{% else %}
<div class="alert alert-info">
    {{ _('Nessuna tariffa configurata.') }}
</div>
{% endif %}

<a href="{{ url_for('admin.representable') }}" class="btn btn-link">
    <i class="bi bi-arrow-left"></i> {{ _('Torna all\'area admin') }}
</a>
{% endblock %}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_admin_fuel_rates.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add fdp_app/admin/routes.py fdp_app/templates/admin/fuel_rates.html tests/test_admin_fuel_rates.py
git commit -m "feat(admin): GET /admin/fuel-rates lists recent km-rates"
```

---

## Task 5: Add POST handler for inserting a new rate

**Files:**
- Modify: `fdp_app/admin/routes.py`
- Modify: `fdp_app/templates/admin/fuel_rates.html` (add the form)
- Modify: `tests/test_admin_fuel_rates.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_admin_fuel_rates.py`:

```python
def test_fuel_rates_create(client, mock_rate_repo):
    _login_admin(client)
    mock_rate_repo.insert.return_value = 77
    response = client.post(
        "/admin/fuel-rates",
        data={
            "avg_consumption_km_l": "15.00",
            "avg_fuel_price_eur_l": "1.700",
            "valid_from": "2026-06-01",
            "valid_to": "2026-12-31",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    mock_rate_repo.insert.assert_called_once()
    kwargs = mock_rate_repo.insert.call_args.kwargs
    assert kwargs["avg_consumption_km_l"] == pytest.approx(15.0)
    assert kwargs["avg_fuel_price_eur_l"] == pytest.approx(1.700)
    assert kwargs["valid_from"] == date(2026, 6, 1)
    assert kwargs["valid_to"] == date(2026, 12, 31)
    assert kwargs["user_sys"] == "Rossi Mario"


def test_fuel_rates_create_without_valid_to(client, mock_rate_repo):
    _login_admin(client)
    mock_rate_repo.insert.return_value = 78
    response = client.post(
        "/admin/fuel-rates",
        data={
            "avg_consumption_km_l": "15.00",
            "avg_fuel_price_eur_l": "1.700",
            "valid_from": "2026-06-01",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert mock_rate_repo.insert.call_args.kwargs["valid_to"] is None
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python -m pytest tests/test_admin_fuel_rates.py::test_fuel_rates_create tests/test_admin_fuel_rates.py::test_fuel_rates_create_without_valid_to -v`
Expected: FAIL — `405 Method Not Allowed` (no POST handler yet).

- [ ] **Step 3: Add the POST handler**

In `fdp_app/admin/routes.py`, append after the `fuel_rates` GET handler:

```python
@bp.route("/fuel-rates", methods=["POST"])
@login_required
@admin_required
def fuel_rates_create():
    db = current_app.config["_db"]
    repo = RateRepo(db)
    try:
        consumption = float(request.form.get("avg_consumption_km_l") or "")
    except ValueError:
        flash(_("Consumo (km/L) non valido."), "danger")
        return redirect(url_for("admin.fuel_rates"))
    if consumption <= 0:
        flash(_("Consumo (km/L) deve essere positivo."), "danger")
        return redirect(url_for("admin.fuel_rates"))
    try:
        fuel_price = float(request.form.get("avg_fuel_price_eur_l") or "")
    except ValueError:
        flash(_("Prezzo carburante (EUR/L) non valido."), "danger")
        return redirect(url_for("admin.fuel_rates"))
    if fuel_price <= 0:
        flash(_("Prezzo carburante (EUR/L) deve essere positivo."), "danger")
        return redirect(url_for("admin.fuel_rates"))
    valid_from_raw = request.form.get("valid_from") or ""
    valid_to_raw = request.form.get("valid_to") or ""
    try:
        valid_from = _date.fromisoformat(valid_from_raw)
    except ValueError:
        flash(_("Data 'valido da' non valida."), "danger")
        return redirect(url_for("admin.fuel_rates"))
    valid_to = None
    if valid_to_raw:
        try:
            valid_to = _date.fromisoformat(valid_to_raw)
        except ValueError:
            flash(_("Data 'valido fino a' non valida."), "danger")
            return redirect(url_for("admin.fuel_rates"))
        if valid_to < valid_from:
            flash(_("'Valido fino a' non puo' essere precedente a 'valido da'."), "danger")
            return redirect(url_for("admin.fuel_rates"))
    try:
        new_id = repo.insert(
            avg_consumption_km_l=consumption,
            avg_fuel_price_eur_l=fuel_price,
            valid_from=valid_from,
            valid_to=valid_to,
            user_sys=session.get("full_name") or "admin",
        )
    except Exception as exc:
        # UNIQUE(ValidFrom) violation surfaces here as pyodbc.IntegrityError.
        if "UX_Rates_ValidFrom" in str(exc) or "UNIQUE" in str(exc).upper():
            flash(_("Esiste gia\' una tariffa con questo 'valido da'."), "danger")
            return redirect(url_for("admin.fuel_rates"))
        raise
    current_app.logger.info(
        "Fuel rate inserted: user_id=%s rate_id=%s consumption=%s price=%s from=%s to=%s",
        session.get("user_id"), new_id, consumption, fuel_price, valid_from, valid_to,
    )
    flash(_("Tariffa inserita (consumo=%(c).2f km/L, prezzo=%(p).3f EUR/L).",
            c=consumption, p=fuel_price), "success")
    return redirect(url_for("admin.fuel_rates"))
```

- [ ] **Step 4: Add the form to the template**

In `fdp_app/templates/admin/fuel_rates.html`, insert this block between the introductory `<p class="text-muted">` and the `<h4>` for the table:

```jinja
<h4 class="mt-4">{{ _('Inserisci nuova tariffa') }}</h4>
<form method="post" action="{{ url_for('admin.fuel_rates_create') }}" class="row g-2 mb-4">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <div class="col-md-3">
        <label class="form-label">{{ _('Consumo medio (km/L)') }}</label>
        <input type="number" name="avg_consumption_km_l" class="form-control"
               step="0.01" min="0.01" required placeholder="15.00">
    </div>
    <div class="col-md-3">
        <label class="form-label">{{ _('Prezzo medio carburante (EUR/L)') }}</label>
        <input type="number" name="avg_fuel_price_eur_l" class="form-control"
               step="0.001" min="0.001" required placeholder="1.700">
    </div>
    <div class="col-md-2">
        <label class="form-label">{{ _('Valido da') }}</label>
        <input type="date" name="valid_from" class="form-control" required>
    </div>
    <div class="col-md-2">
        <label class="form-label">{{ _('Valido fino a (opzionale)') }}</label>
        <input type="date" name="valid_to" class="form-control">
    </div>
    <div class="col-md-2 d-flex align-items-end">
        <button type="submit" class="btn btn-primary w-100">
            <i class="bi bi-plus-circle"></i> {{ _('Salva tariffa') }}
        </button>
    </div>
</form>
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_admin_fuel_rates.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add fdp_app/admin/routes.py fdp_app/templates/admin/fuel_rates.html tests/test_admin_fuel_rates.py
git commit -m "feat(admin): POST /admin/fuel-rates inserts new km-rate version"
```

---

## Task 6: Reject invalid input in POST

**Files:**
- Modify: `tests/test_admin_fuel_rates.py`

The POST handler from Task 5 already implements the validation branches. This task locks them in with regression tests.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_admin_fuel_rates.py`:

```python
def test_fuel_rates_create_rejects_invalid_consumption(client, mock_rate_repo):
    _login_admin(client)
    response = client.post(
        "/admin/fuel-rates",
        data={
            "avg_consumption_km_l": "not-a-number",
            "avg_fuel_price_eur_l": "1.7",
            "valid_from": "2026-06-01",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    mock_rate_repo.insert.assert_not_called()


def test_fuel_rates_create_rejects_non_positive_consumption(client, mock_rate_repo):
    _login_admin(client)
    response = client.post(
        "/admin/fuel-rates",
        data={
            "avg_consumption_km_l": "0",
            "avg_fuel_price_eur_l": "1.7",
            "valid_from": "2026-06-01",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    mock_rate_repo.insert.assert_not_called()


def test_fuel_rates_create_rejects_non_positive_price(client, mock_rate_repo):
    _login_admin(client)
    response = client.post(
        "/admin/fuel-rates",
        data={
            "avg_consumption_km_l": "15",
            "avg_fuel_price_eur_l": "-0.5",
            "valid_from": "2026-06-01",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    mock_rate_repo.insert.assert_not_called()


def test_fuel_rates_create_rejects_invalid_valid_from(client, mock_rate_repo):
    _login_admin(client)
    response = client.post(
        "/admin/fuel-rates",
        data={
            "avg_consumption_km_l": "15",
            "avg_fuel_price_eur_l": "1.7",
            "valid_from": "not-a-date",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    mock_rate_repo.insert.assert_not_called()


def test_fuel_rates_create_rejects_valid_to_before_valid_from(client, mock_rate_repo):
    _login_admin(client)
    response = client.post(
        "/admin/fuel-rates",
        data={
            "avg_consumption_km_l": "15",
            "avg_fuel_price_eur_l": "1.7",
            "valid_from": "2026-06-01",
            "valid_to": "2026-05-15",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    mock_rate_repo.insert.assert_not_called()
```

- [ ] **Step 2: Run the tests to verify they pass**

Run: `python -m pytest tests/test_admin_fuel_rates.py -v`
Expected: all 10 tests PASS (the validation branches in Task 5 already cover these).

- [ ] **Step 3: Commit**

```bash
git add tests/test_admin_fuel_rates.py
git commit -m "test(admin): pin POST /admin/fuel-rates validation contract"
```

---

## Task 7: Handle duplicate `ValidFrom` (`UX_Rates_ValidFrom`) gracefully

**Files:**
- Modify: `tests/test_admin_fuel_rates.py`

The POST handler from Task 5 already catches the unique-violation exception and flashes a clear message. This task locks the behaviour with a regression test that simulates the exception from the repo.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_admin_fuel_rates.py`:

```python
def test_fuel_rates_create_handles_duplicate_valid_from(client, mock_rate_repo):
    _login_admin(client)
    mock_rate_repo.insert.side_effect = Exception(
        "Violation of UNIQUE KEY constraint 'UX_Rates_ValidFrom'."
    )
    response = client.post(
        "/admin/fuel-rates",
        data={
            "avg_consumption_km_l": "15",
            "avg_fuel_price_eur_l": "1.7",
            "valid_from": "2026-06-01",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    mock_rate_repo.insert.assert_called_once()
    # the page renders and does not 500
    assert b"Tariffe rimborso km" in response.data
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `python -m pytest tests/test_admin_fuel_rates.py::test_fuel_rates_create_handles_duplicate_valid_from -v`
Expected: PASS (the `except Exception` branch added in Task 5 catches the unique-violation message).

- [ ] **Step 3: Verify a non-matching exception still propagates (sanity)**

Append:

```python
def test_fuel_rates_create_propagates_unrelated_db_errors(client, mock_rate_repo):
    _login_admin(client)
    mock_rate_repo.insert.side_effect = Exception("network timeout")
    # With TESTING=True Flask re-raises unhandled exceptions from the test
    # client instead of returning a 500 — we assert that propagation.
    with pytest.raises(Exception, match="network timeout"):
        client.post(
            "/admin/fuel-rates",
            data={
                "avg_consumption_km_l": "15",
                "avg_fuel_price_eur_l": "1.7",
                "valid_from": "2026-06-01",
            },
        )
```

Run: `python -m pytest tests/test_admin_fuel_rates.py -v`
Expected: all 12 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_admin_fuel_rates.py
git commit -m "test(admin): fuel-rates handles duplicate ValidFrom violations"
```

---

## Task 8: Add nav link from `/admin/representable`

**Files:**
- Modify: `fdp_app/templates/admin/representable.html`
- Modify: `tests/test_admin_fuel_rates.py` (one extra test that loads `/admin/representable` and asserts the link is present)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_admin_fuel_rates.py`:

```python
def test_representable_page_links_to_fuel_rates(client):
    with patch("fdp_app.admin.routes.EmployeeRepo") as emp_cls:
        emp_instance = MagicMock()
        emp_instance.find_representable_for.return_value = []
        emp_cls.return_value = emp_instance
        _login_admin(client)
        response = client.get("/admin/representable")
    assert response.status_code == 200
    assert b"/admin/fuel-rates" in response.data
    assert b"fuel-pump" in response.data
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_admin_fuel_rates.py::test_representable_page_links_to_fuel_rates -v`
Expected: FAIL — `b'/admin/fuel-rates' not in response.data`.

- [ ] **Step 3: Add the link to `representable.html`**

Open `fdp_app/templates/admin/representable.html`. After the existing `<a href="{{ url_for('admin.bnr_rates') }}" ...>` link (around line 50-52), add:

```jinja
<a href="{{ url_for('admin.fuel_rates') }}" class="btn btn-link mt-3">
    <i class="bi bi-fuel-pump"></i> {{ _('Gestisci tariffe €/km') }}
</a>
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_admin_fuel_rates.py::test_representable_page_links_to_fuel_rates -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add fdp_app/templates/admin/representable.html tests/test_admin_fuel_rates.py
git commit -m "feat(admin): link fuel-rates page from representable"
```

---

## Task 9: Full suite sanity-check and final commit (i18n marker)

**Files:**
- None modified by default.

This is a final verification step. If `pybabel` is available locally and used by the project, regenerate the `.pot` so the new strings are captured. Otherwise, skip.

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest -q`
Expected: all tests PASS. If anything else regressed (e.g., a snapshot test), investigate before proceeding.

- [ ] **Step 2: Optional — regenerate the message catalog**

Check whether the project has a babel config. If `babel.cfg` exists at the repo root:

Run: `pybabel extract -F babel.cfg -o messages.pot fdp_app`
Then `pybabel update -i messages.pot -d fdp_app/translations` if a `translations/` directory exists with locale subfolders.

If `pybabel` is not installed or the project doesn't use it, skip this step entirely. The strings in the new template/routes are still rendered correctly (Flask-Babel falls back to the source string when no translation exists).

- [ ] **Step 3: Commit any catalog changes (if step 2 ran)**

```bash
git add messages.pot fdp_app/translations
git commit -m "i18n: extract new fuel-rates strings"
```

If nothing changed, skip the commit.

- [ ] **Step 4: Manual smoke test (optional)**

Start the app locally and visit `/admin/representable` → click "Gestisci tariffe €/km" → submit a new rate with valid values → confirm it appears in the table with `€/km` computed correctly. Try submitting a duplicate `valid_from` → confirm the flash message appears and no 500.

---

## Verification Summary

After Task 9 the working tree contains:

- `fdp_app/repos/rate_repo.py` — `Rate` dataclass with audit fields; `insert` and `list_recent` methods.
- `fdp_app/admin/routes.py` — `fuel_rates` (GET) and `fuel_rates_create` (POST) endpoints.
- `fdp_app/templates/admin/fuel_rates.html` — new page with form + history table.
- `fdp_app/templates/admin/representable.html` — new nav link.
- `tests/test_rate_repo.py` — 7 tests (3 existing + 4 new).
- `tests/test_admin_fuel_rates.py` — 13 tests (1 auth + 2 list + 2 success + 5 reject + 2 dup + 1 nav).

Spec sections coverage:
- §3 Decisioni → Tasks 1-3 (schema invariato, insert-only), Task 4 (admin_required), Task 8 (nav link).
- §4 Architettura → enforced by the File Structure table.
- §5 Repository → Tasks 1, 2, 3.
- §6 Route → Tasks 4 (GET), 5 (POST), 6 (validation), 7 (IntegrityError).
- §7 Template → Tasks 4 (table) and 5 (form).
- §8 Navigazione → Task 8.
- §9 Test → distributed across all tasks; final count in Task 9.
- §10 YAGNI → nothing in the plan implements edit/delete/auto-close, so the YAGNI scope is upheld.
- §11 Rischi → mitigated by Task 7 (duplicate `ValidFrom`) and Task 1's default-`None` defence on `Rate`.
