# Admin History & Export Row Cap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cap `/admin/history` and `/admin/export` at 500 rows enforced at the SQL layer, with a visible warning banner in the template and both a `-truncated` filename suffix and an in-sheet banner row in the XLSX export when the cap is hit.

**Architecture:** Add an optional `limit` kwarg to `PathTrackRepo.list_for_sub_cdc` that injects `SELECT TOP (?)` into the existing SQL template. Routes pass `limit=MAX_HISTORY_ROWS` (a module constant in `routes.py`), fetch `limit+1` to detect cap hits, slice down to `limit`, and propagate a `truncated` boolean to template and XLSX builder. The XLSX builder shifts its layout by one row when truncated to make room for a banner.

**Tech Stack:** Python 3.11+, Flask, pyodbc (SQL Server), openpyxl, pytest, Jinja2, Bootstrap 5.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `fdp_app/repos/pathtrack_repo.py` | DB access for PathTracks. Add SQL TOP support. | Modify |
| `fdp_app/admin/routes.py` | Admin route handlers. Owns `MAX_HISTORY_ROWS`. | Modify |
| `fdp_app/admin/service.py` | XLSX builder. Accept truncation banner kwarg. | Modify |
| `fdp_app/templates/admin/history.html` | History page template. Render warning alert. | Modify |
| `tests/test_admin_routes.py` | Route tests. Add cap-related cases. | Modify |
| `tests/test_admin_export.py` | XLSX + export route tests. Add cap-related cases. | Modify |

Each task is one cohesive change. Tasks 1–4 are sequenced because Task 4 (template) depends on Task 3 (routes passing `truncated` in the context), and Task 3 depends on Task 2 (XLSX builder accepting `truncated`), which depends on Task 1 (repo accepting `limit`).

---

## Task 1: Add `limit` kwarg to `PathTrackRepo.list_for_sub_cdc`

**Files:**
- Modify: `fdp_app/repos/pathtrack_repo.py` (the `_QUERY_LIST_SUB_CDC` string and the `list_for_sub_cdc` method)
- Test: `tests/test_admin_routes.py` (verifies repo is called with `limit=500` from the route — the repo itself is mocked in existing tests, so we cover behavior via route tests in later tasks)

This task is non-TDD because it changes a SQL template that is only exercised against a real SQL Server, and the existing test suite mocks the repo entirely. We verify backward compatibility by running the full test suite — every existing test that uses the repo passes `limit=None` (the default) and expects the existing behavior.

- [ ] **Step 1: Read the current state of `_QUERY_LIST_SUB_CDC` and `list_for_sub_cdc`**

Open `fdp_app/repos/pathtrack_repo.py`. The template currently looks like:

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
```

- [ ] **Step 2: Add a `/*TOP*/` marker to the template**

Replace the `_QUERY_LIST_SUB_CDC` string with:

```python
_QUERY_LIST_SUB_CDC = """
SELECT /*TOP*/
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
```

- [ ] **Step 3: Add `limit` kwarg and template substitution to `list_for_sub_cdc`**

Replace the existing `list_for_sub_cdc` method (currently around lines 261–317) with:

```python
    def list_for_sub_cdc(
        self,
        *,
        sub_cdc_id: int,
        year: int | None = None,
        month: int | None = None,
        reimbursement_type: str | None = None,
        limit: int | None = None,
    ) -> list:
        """Lists all path tracks for a SubCdcId, optionally filtered by year/month/type.

        The JOIN follows COALESCE(InBehalfOfId, EmployeeHireHistoryId) so that
        delegated entries are attributed to the represented employee.

        Args:
            limit: If given, the SQL query uses TOP (limit) to cap rows at the
                database level. Callers that need to detect truncation should
                pass `cap + 1` and check `len(rows) > cap` on the result.
        """
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
        if limit is not None:
            sql = sql.replace("/*TOP*/", "TOP (?)")
            params.insert(0, limit)
        else:
            sql = sql.replace("/*TOP*/", "")
        cursor = self._open_cursor()
        try:
            cursor.execute(sql, *params)
            rows = cursor.fetchall()
        finally:
            cursor.close()
        result = []
        for r in rows:
            ptrow = PathTrackRow(
                path_track_id=r[0],
                registry_id=r[1] if r[1] is not None else None,
                date_path_track=r[2],
                declarated_path_id=r[3],
                in_behalf_of_id=r[4],
                reimbursement_type=r[5].rstrip() if isinstance(r[5], str) else r[5],
                number_of_trips=r[6],
                road_km=float(r[7]),
                rate_id_used=r[8],
                taxi_total_eur=float(r[9]) if r[9] is not None else None,
                computed_amount_eur=float(r[10]),
                status=r[11].rstrip() if isinstance(r[11], str) else r[11],
                submitted_on=r[12],
            )
            result.append(PathTrackWithEmployee(
                row=ptrow,
                employee_surname=r[13],
                employee_name=r[14],
            ))
        return result
```

Notes:
- SQL Server requires `TOP (?)` (parentheses around the `?`) when binding the value as a parameter — `TOP ?` is a syntax error.
- `params.insert(0, limit)` puts the `TOP` parameter ahead of `sub_cdc_id` because in the rewritten SQL, the `?` inside `TOP (?)` appears before the `?` for `s.SubCdcId`. pyodbc binds parameters by position, so order matters.
- The repo accepts the cap value as-is. Routes pass `cap + 1` so they can detect truncation by checking `len(rows) > cap`; the docstring documents this contract.

- [ ] **Step 4: Run the full test suite to confirm backward compatibility**

Run: `pytest -q`
Expected: All existing tests pass. The repo's new `limit` kwarg defaults to `None`, so no behavior change for any current caller.

- [ ] **Step 5: Commit**

```bash
git add fdp_app/repos/pathtrack_repo.py
git commit -m "feat(repo): add optional limit kwarg to list_for_sub_cdc

Adds SQL TOP support via a /*TOP*/ template marker. Default behavior
unchanged — limit defaults to None and no TOP clause is injected.
Callers wanting truncation detection should pass cap + 1 and check
len(rows) > cap."
```

---

## Task 2: Add `truncated` + `max_rows` kwargs to `build_xlsx`

**Files:**
- Modify: `fdp_app/admin/service.py`
- Test: `tests/test_admin_export.py` — add 2 new tests

- [ ] **Step 1: Write the failing test for the banner row**

Append to `tests/test_admin_export.py` (after `test_build_xlsx_handles_draft_with_null_registry_and_submitted_on`):

```python
def test_build_xlsx_injects_banner_when_truncated():
    """When truncated=True, row 1 is a banner mentioning the cap; headers shift to row 2."""
    entries = [_entry()]
    xlsx_bytes = build_xlsx(
        entries, year=2026, month=4, month_name="Aprile",
        truncated=True, max_rows=500,
    )
    wb = load_workbook(BytesIO(xlsx_bytes))
    ws = wb.active
    banner = ws.cell(row=1, column=1).value or ""
    assert "AVVISO" in banner
    assert "troncati" in banner
    assert "500" in banner
    # Headers shifted to row 2
    header_row = [c.value for c in ws[2]]
    assert "Cognome" in header_row
    # Data starts at row 3
    assert ws.cell(row=3, column=1).value == "Rossi"


def test_build_xlsx_requires_max_rows_when_truncated():
    """If truncated=True but max_rows is None, the builder should raise."""
    with pytest.raises((ValueError, AssertionError)):
        build_xlsx(
            [_entry()], year=2026, month=4, month_name="Aprile",
            truncated=True, max_rows=None,
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_admin_export.py::test_build_xlsx_injects_banner_when_truncated tests/test_admin_export.py::test_build_xlsx_requires_max_rows_when_truncated -v`

Expected: Both FAIL. The first fails because `build_xlsx` doesn't accept `truncated` / `max_rows` kwargs (`TypeError: unexpected keyword argument`). The second fails for the same reason.

- [ ] **Step 3: Update `build_xlsx` to accept and use the new kwargs**

Replace the entire contents of `fdp_app/admin/service.py` with:

```python
"""Helpers admin: generazione XLSX in memoria."""
from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter


def build_xlsx(
    rows,
    *,
    year: int,
    month: int,
    month_name: str,
    truncated: bool = False,
    max_rows: int | None = None,
) -> bytes:
    """Genera un XLSX con una riga per PathTrackWithEmployee.

    rows: iterable di PathTrackWithEmployee
    truncated: True se la lista è stata troncata al cap. Inserisce una riga
        banner all'inizio del foglio.
    max_rows: cap utilizzato (richiesto quando truncated=True, ignorato altrimenti)
    """
    if truncated and max_rows is None:
        raise ValueError("max_rows must be set when truncated=True")

    wb = Workbook()
    ws = wb.active
    ws.title = f"{month_name} {year}"

    headers = [
        "Cognome", "Nome", "Tipo", "Stato", "N. Viaggi A/R", "Km one-way",
        "Importo EUR", "N. Registro", "Data invio",
    ]

    if truncated:
        banner_text = (
            f"AVVISO: risultati troncati a {max_rows} righe. "
            "Restringere i filtri per dati completi."
        )
        ws.append([banner_text])
        ws.merge_cells(
            start_row=1, start_column=1,
            end_row=1, end_column=len(headers),
        )
        banner_cell = ws.cell(row=1, column=1)
        banner_cell.font = Font(bold=True, color="000000")
        banner_cell.fill = PatternFill("solid", fgColor="FFF3CD")
        banner_cell.alignment = Alignment(horizontal="center", vertical="center")
        header_row_idx = 2
    else:
        header_row_idx = 1

    ws.append(headers)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="0B2A5B")
    header_align = Alignment(horizontal="center")
    for cell in ws[header_row_idx]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

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

    # Auto-width approssimativo. Skip the banner row (merged cells confuse the
    # per-column max-length calc), so iterate from the header row down.
    for col_idx in range(1, len(headers) + 1):
        max_len = 0
        for row_idx in range(header_row_idx, ws.max_row + 1):
            v = ws.cell(row=row_idx, column=col_idx).value
            if v is not None:
                max_len = max(max_len, len(str(v)))
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 2, 50)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
```

Note: The auto-width loop changed from iterating `ws.columns` to iterating column indices. The original loop used `col[0].column_letter` which fails for merged cells (the merged banner row would make `col` contain `MergedCell` instances without a proper `column_letter`). Iterating by index avoids this.

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `pytest tests/test_admin_export.py::test_build_xlsx_injects_banner_when_truncated tests/test_admin_export.py::test_build_xlsx_requires_max_rows_when_truncated -v`

Expected: Both PASS.

- [ ] **Step 5: Run existing XLSX tests to confirm no regression**

Run: `pytest tests/test_admin_export.py -v`

Expected: All tests pass, including the existing `test_build_xlsx_generates_valid_workbook`, `test_build_xlsx_handles_empty_rows`, and `test_build_xlsx_handles_draft_with_null_registry_and_submitted_on` (these all use the default `truncated=False`, so layout is unchanged: header row 1, data row 2).

- [ ] **Step 6: Commit**

```bash
git add fdp_app/admin/service.py tests/test_admin_export.py
git commit -m "feat(admin): build_xlsx supports truncation banner

Adds truncated/max_rows kwargs to build_xlsx. When truncated=True, a
merged banner row is inserted at row 1 announcing the cap, and header/
data shift down by one row. Default behavior (truncated=False) is
unchanged — header at row 1, data at row 2.

Refactors the auto-width loop to iterate by column index, which is
necessary because openpyxl's ws.columns yields MergedCell instances
for merged ranges, breaking the original col[0].column_letter access."
```

---

## Task 3: Wire `MAX_HISTORY_ROWS` cap into `/admin/history` and `/admin/export` routes

**Files:**
- Modify: `fdp_app/admin/routes.py`
- Test: `tests/test_admin_routes.py` (history-side), `tests/test_admin_export.py` (export-side)

- [ ] **Step 1: Write failing tests for the history route**

Append to `tests/test_admin_routes.py` (after `test_history_filters_by_type`):

```python
def test_history_passes_limit_to_repo(client, mock_pathtrack_repo_admin):
    """history() should call list_for_sub_cdc with limit=MAX_HISTORY_ROWS + 1."""
    from fdp_app.admin.routes import MAX_HISTORY_ROWS
    _login_admin(client)
    response = client.get("/admin/history")
    assert response.status_code == 200
    kwargs = mock_pathtrack_repo_admin.list_for_sub_cdc.call_args.kwargs
    assert kwargs["limit"] == MAX_HISTORY_ROWS + 1


def test_history_shows_warning_when_truncated(client, mock_pathtrack_repo_admin):
    """When repo returns more than the cap, the page shows a truncation alert."""
    from fdp_app.repos.pathtrack_repo import PathTrackRow, PathTrackWithEmployee
    from datetime import date as Date
    _login_admin(client, sub_cdc_id=42)

    def _mk(i: int) -> PathTrackWithEmployee:
        return PathTrackWithEmployee(
            row=PathTrackRow(
                path_track_id=i, registry_id=None, date_path_track=Date(2026, 5, 1),
                declarated_path_id=99, in_behalf_of_id=None,
                reimbursement_type="CARBURANTE", number_of_trips=1, road_km=1.0,
                rate_id_used=3, taxi_total_eur=None, computed_amount_eur=1.0,
                status="DRAFT", submitted_on=None,
            ),
            employee_surname=f"Dip{i}", employee_name="X",
        )

    # Patch MAX_HISTORY_ROWS down so we don't need 500 mock rows
    with patch("fdp_app.admin.routes.MAX_HISTORY_ROWS", 2):
        mock_pathtrack_repo_admin.list_for_sub_cdc.return_value = [_mk(i) for i in range(3)]
        response = client.get("/admin/history")
        assert response.status_code == 200
        assert b"troncati" in response.data.lower() or b"troncati" in response.data
        # Only the first 2 rows are rendered
        assert b"Dip0" in response.data
        assert b"Dip1" in response.data
        assert b"Dip2" not in response.data


def test_history_no_warning_when_under_cap(client, mock_pathtrack_repo_admin):
    """When repo returns <= cap, no truncation alert appears."""
    from fdp_app.repos.pathtrack_repo import PathTrackRow, PathTrackWithEmployee
    from datetime import date as Date
    _login_admin(client)
    mock_pathtrack_repo_admin.list_for_sub_cdc.return_value = [
        PathTrackWithEmployee(
            row=PathTrackRow(
                path_track_id=1, registry_id=None, date_path_track=Date(2026, 5, 1),
                declarated_path_id=99, in_behalf_of_id=None,
                reimbursement_type="CARBURANTE", number_of_trips=1, road_km=1.0,
                rate_id_used=3, taxi_total_eur=None, computed_amount_eur=1.0,
                status="DRAFT", submitted_on=None,
            ),
            employee_surname="Solo", employee_name="X",
        ),
    ]
    response = client.get("/admin/history")
    assert response.status_code == 200
    assert b"troncati" not in response.data.lower()
```

- [ ] **Step 2: Write failing tests for the export route**

Append to `tests/test_admin_export.py` (after `test_export_rejects_missing_year`):

```python
def test_export_passes_limit_to_repo(client, mock_pt_repo_export):
    """export() should call list_for_sub_cdc with limit=MAX_HISTORY_ROWS + 1."""
    from fdp_app.admin.routes import MAX_HISTORY_ROWS
    _login_admin(client)
    response = client.get("/admin/export?year=2026&month=4")
    assert response.status_code == 200
    kwargs = mock_pt_repo_export.list_for_sub_cdc.call_args.kwargs
    assert kwargs["limit"] == MAX_HISTORY_ROWS + 1


def test_export_filename_has_truncated_suffix_when_capped(client, mock_pt_repo_export):
    """When the result exceeds the cap, filename gets a -truncated suffix."""
    _login_admin(client)
    with patch("fdp_app.admin.routes.MAX_HISTORY_ROWS", 2):
        mock_pt_repo_export.list_for_sub_cdc.return_value = [
            _entry(path_track_id=i) for i in range(3)
        ]
        response = client.get("/admin/export?year=2026&month=4")
        assert response.status_code == 200
        cd = response.headers.get("Content-Disposition", "")
        assert "fogli-di-percorso-2026-04-truncated.xlsx" in cd


def test_export_filename_unchanged_when_under_cap(client, mock_pt_repo_export):
    """When under the cap, filename has no -truncated suffix."""
    _login_admin(client)
    mock_pt_repo_export.list_for_sub_cdc.return_value = [_entry()]
    response = client.get("/admin/export?year=2026&month=4")
    assert response.status_code == 200
    cd = response.headers.get("Content-Disposition", "")
    assert "fogli-di-percorso-2026-04.xlsx" in cd
    assert "truncated" not in cd
```

- [ ] **Step 3: Run all 6 new tests to verify they fail**

Run: `pytest tests/test_admin_routes.py::test_history_passes_limit_to_repo tests/test_admin_routes.py::test_history_shows_warning_when_truncated tests/test_admin_routes.py::test_history_no_warning_when_under_cap tests/test_admin_export.py::test_export_passes_limit_to_repo tests/test_admin_export.py::test_export_filename_has_truncated_suffix_when_capped tests/test_admin_export.py::test_export_filename_unchanged_when_under_cap -v`

Expected: All 6 FAIL. The `passes_limit_to_repo` tests fail because `MAX_HISTORY_ROWS` doesn't exist yet (ImportError). The other tests fail because the truncation logic isn't implemented.

- [ ] **Step 4: Update `routes.py` to add the constant and wire truncation**

Replace the entire contents of `fdp_app/admin/routes.py` with:

```python
"""Route amministrative (rappresentanza colleghi + storico + export)."""
from __future__ import annotations

from flask import (
    Blueprint, Response, abort, current_app, render_template, request, session,
)
from fdp_app.repos.doc_repo import PathTrackDocRepo

from fdp_app.admin.service import build_xlsx
from fdp_app.auth.decorators import admin_required, login_required
from fdp_app.repos.employee_repo import EmployeeRepo
from fdp_app.repos.pathtrack_repo import PathTrackRepo

bp = Blueprint("admin", __name__, url_prefix="/admin")

# Cap on the number of history rows returned to admins in a single page or
# export. Enforced at the SQL layer via TOP (?). When the cap is hit, the
# template shows a warning banner and the XLSX export gets a -truncated
# filename suffix plus an in-sheet banner row.
MAX_HISTORY_ROWS = 500

_MONTH_NAMES_IT = [
    "", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]


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
        limit=MAX_HISTORY_ROWS + 1,
    )
    truncated = len(rows) > MAX_HISTORY_ROWS
    if truncated:
        rows = rows[:MAX_HISTORY_ROWS]
    return render_template(
        "admin/history.html",
        rows=rows,
        year=year, month=month, type=reimbursement_type,
        month_names=_MONTH_NAMES_IT,
        truncated=truncated,
        max_rows=MAX_HISTORY_ROWS,
    )


@bp.route("/pathtracks/<int:path_track_id>", methods=["GET"])
@login_required
@admin_required
def view_pathtrack(path_track_id: int):
    db = current_app.config["_db"]
    pathtrack_repo = PathTrackRepo(db)
    row = pathtrack_repo.find_by_id_in_sub_cdc(
        path_track_id=path_track_id,
        sub_cdc_id=session["sub_cdc_id"],
    )
    if row is None:
        abort(404)
    doc_repo = PathTrackDocRepo(db)
    docs = doc_repo.list_for_pathtrack(path_track_id=path_track_id)
    return render_template(
        "admin/view_pathtrack.html",
        row=row,
        docs=docs,
        month_label=_MONTH_NAMES_IT[row.date_path_track.month],
    )


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
        limit=MAX_HISTORY_ROWS + 1,
    )
    truncated = len(rows) > MAX_HISTORY_ROWS
    if truncated:
        rows = rows[:MAX_HISTORY_ROWS]
    xlsx_bytes = build_xlsx(
        rows, year=year, month=month, month_name=_MONTH_NAMES_IT[month],
        truncated=truncated,
        max_rows=MAX_HISTORY_ROWS if truncated else None,
    )
    suffix = "-truncated" if truncated else ""
    filename = f"fogli-di-percorso-{year:04d}-{month:02d}{suffix}.xlsx"
    return Response(
        xlsx_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 5: Run the 6 new tests to verify they pass**

Run: `pytest tests/test_admin_routes.py::test_history_passes_limit_to_repo tests/test_admin_routes.py::test_history_shows_warning_when_truncated tests/test_admin_routes.py::test_history_no_warning_when_under_cap tests/test_admin_export.py::test_export_passes_limit_to_repo tests/test_admin_export.py::test_export_filename_has_truncated_suffix_when_capped tests/test_admin_export.py::test_export_filename_unchanged_when_under_cap -v`

Expected: 5 PASS, 1 FAIL — `test_history_shows_warning_when_truncated` still fails because the template doesn't yet render the warning banner (that's Task 4).

If 5/6 pass with the expected one failure, proceed to Task 4. If anything else fails, debug before continuing.

- [ ] **Step 6: Run the full suite to check for regressions**

Run: `pytest -q`

Expected: All tests pass EXCEPT `test_history_shows_warning_when_truncated` (which is unblocked by Task 4). All previously passing tests still pass — existing tests don't pass `limit`, but they assert on call kwargs they care about, not on the absence of `limit`, so they're unaffected. Existing export tests assert `fogli-di-percorso-2026-04.xlsx` is in the Content-Disposition; this remains true when `truncated=False`.

- [ ] **Step 7: Commit**

```bash
git add fdp_app/admin/routes.py tests/test_admin_routes.py tests/test_admin_export.py
git commit -m "feat(admin): cap history & export at MAX_HISTORY_ROWS=500

Both /admin/history and /admin/export now pass limit=MAX_HISTORY_ROWS+1
to the repo, detect truncation via len(rows) > cap, slice down to cap,
and propagate a truncated flag downstream. Export filename gets a
-truncated suffix when capped. Template warning still pending (Task 4)."
```

---

## Task 4: Render truncation banner in `admin/history.html`

**Files:**
- Modify: `fdp_app/templates/admin/history.html`
- Test: `tests/test_admin_routes.py` — `test_history_shows_warning_when_truncated` (already written in Task 3) unblocks here

- [ ] **Step 1: Verify the test is currently failing**

Run: `pytest tests/test_admin_routes.py::test_history_shows_warning_when_truncated -v`

Expected: FAIL — the response does not contain `"troncati"`.

- [ ] **Step 2: Add the alert block to the template**

Open `fdp_app/templates/admin/history.html`. Insert the following block immediately after the closing `</form>` tag (around line 42) and before the `{% if rows %}` block:

```html
{% if truncated %}
<div class="alert alert-warning d-flex align-items-center" role="alert">
    <i class="bi bi-exclamation-triangle-fill me-2"></i>
    <div>
        Risultati troncati a {{ max_rows }} righe.
        Restringere i filtri (anno, mese, tipo) per ottenere dati completi.
    </div>
</div>
{% endif %}
```

The result is that the template's `<body>` flow becomes:
- Filters form
- (new) Truncation warning, only when `truncated`
- Results table or empty-state alert
- Back link

- [ ] **Step 3: Run the failing test to verify it now passes**

Run: `pytest tests/test_admin_routes.py::test_history_shows_warning_when_truncated -v`

Expected: PASS — response body contains `"troncati"` and includes `Dip0`/`Dip1` but not `Dip2`.

- [ ] **Step 4: Run the full suite to confirm no regressions**

Run: `pytest -q`

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add fdp_app/templates/admin/history.html
git commit -m "feat(admin): render truncation warning in history template

When the route flags truncated=True, the page now shows a Bootstrap
alert-warning above the results table with the cap value and guidance
to narrow filters."
```

---

## Task 5: Final verification pass

**Files:** None (verification only).

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`

Expected: All tests pass (counts match: pre-change count + 9 new tests = 3 in test_admin_routes.py + 6 in test_admin_export.py).

- [ ] **Step 2: Manually verify by reading the diff**

Run: `git log --oneline -5`

Expected: Five commits in order — the spec commit (already on the branch from brainstorming), Task 1 (repo), Task 2 (build_xlsx), Task 3 (routes), Task 4 (template).

Run: `git diff main...HEAD --stat`

Expected: Six files changed (the repo, routes, service, template, two test files), matching the file-structure table.

- [ ] **Step 3: Smoke-test the cap-disabled path mentally**

Re-read `fdp_app/repos/pathtrack_repo.py::list_for_sub_cdc`. Confirm: when `limit=None`, the SQL template's `/*TOP*/` is replaced with empty string and no parameter is added to `params`. Behavior is identical to before for any caller that doesn't pass `limit`.

- [ ] **Step 4: Final commit (if anything was touched during verification)**

If verification surfaced no changes, skip. Otherwise:

```bash
git add -p   # review each hunk
git commit -m "fix: <whatever verification surfaced>"
```

---

## Self-Review Notes

**Spec coverage check:**

| Spec section | Covered by |
|---|---|
| Module constant `MAX_HISTORY_ROWS = 500` in `routes.py` | Task 3, Step 4 |
| `limit` kwarg on `list_for_sub_cdc` | Task 1 |
| SQL `TOP (?)` injection | Task 1, Step 3 |
| Routes pass `limit+1`, detect via `len > cap`, slice | Task 3, Step 4 |
| `build_xlsx` accepts `truncated` + `max_rows` | Task 2 |
| XLSX banner row at row 1, headers shift to row 2 | Task 2, Step 3 |
| Filename `-truncated` suffix | Task 3, Step 4 (export function) |
| Template `alert-warning` block | Task 4 |
| Italian wording | Task 2 (XLSX banner), Task 4 (template alert) |
| Backward compatibility (`limit=None` ⇒ unchanged) | Task 1, Step 4 (full suite passes); Task 5, Step 3 (mental check) |
| All test cases listed in spec | Task 2 (2 build_xlsx tests), Task 3 (6 route tests), Task 4 (banner rendering verified by Task 3's test) |

**Placeholder scan:** None found. Every code step shows the actual code to write. Every test step shows the actual test. Every command shows what to run and what to expect.

**Type consistency:**
- `MAX_HISTORY_ROWS` referenced consistently across Task 3 (definition) and Task 3 tests (import).
- `build_xlsx(truncated=..., max_rows=...)` consistent between Task 2 (definition) and Task 3 (call site).
- `list_for_sub_cdc(limit=...)` consistent between Task 1 (definition) and Task 3 (call sites).
- Template variables `truncated` and `max_rows` passed in Task 3 (Step 4) match the names used in Task 4's template block.
