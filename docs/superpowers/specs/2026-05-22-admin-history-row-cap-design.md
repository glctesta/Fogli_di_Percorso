# Admin History & Export Row Cap — Design

**Date:** 2026-05-22
**Status:** Approved (pending user spec review)
**Scope:** `/admin/history` GET and `/admin/export` GET

## Problem

`fdp_app/admin/routes.py::history()` and `fdp_app/admin/routes.py::export()` both call `PathTrackRepo.list_for_sub_cdc(...)` without any row limit. For SubCdcs with large headcounts or long history, the result set can grow unbounded — the database returns every matching row, the Flask process renders an arbitrarily large HTML table or builds an arbitrarily large XLSX in memory, and the user has no signal that they are looking at an unfiltered firehose.

## Goal

Cap both routes at **500 rows**, enforced at the SQL layer so the database never returns more than 501 rows. When the cap is hit, surface a visible warning to the user:

- In `/admin/history` — a Bootstrap warning banner above the results table.
- In `/admin/export` — both a `-truncated` suffix in the XLSX filename and a visible banner row at the top of the sheet.

## Non-goals

- Pagination / "page 2" navigation. The cap is a guardrail, not a paging mechanism. The fix to "I want more rows" is "narrow your filters."
- Making the cap user-configurable from the UI.
- Touching the per-employee `list_for_employee` query (only the SubCdc admin query has the unbounded-headcount risk).
- Optimizing the underlying SQL query plan.

## Architecture

### Single source of truth

A module-level constant in `fdp_app/admin/routes.py`:

```python
MAX_HISTORY_ROWS = 500
```

Constant lives in `routes.py` (not `settings`) because:

- Only admin routes consume it.
- Tests patch it via `mock.patch("fdp_app.admin.routes.MAX_HISTORY_ROWS", 2)` to exercise truncation without 500 mock rows.
- Promoting it to settings is a one-line refactor later if needs change.

### Repo change

`PathTrackRepo.list_for_sub_cdc` gains an optional `limit: int | None = None` kwarg.

- When `limit is None` → no `TOP` clause → behavior identical to today (backward compatible).
- When `limit is not None` → SQL becomes `SELECT TOP (?) ...` with `limit + 1` bound as the first positional parameter so the caller can detect truncation by checking `len(rows) > limit`.

The existing `_QUERY_LIST_SUB_CDC` template already uses a `/*FILTERS*/` placeholder; we add a parallel `/*TOP*/` placeholder right after `SELECT` and replace it with either `TOP (?)` or empty string.

### Route changes

Both `history()` and `export()`:

1. Call repo with `limit=MAX_HISTORY_ROWS`.
2. Compute `truncated = len(rows) > MAX_HISTORY_ROWS`.
3. Slice: `rows = rows[:MAX_HISTORY_ROWS]`.
4. Pass `truncated` and `MAX_HISTORY_ROWS` downstream (template / xlsx builder).

For `export()`, when `truncated` is True the filename becomes `fogli-di-percorso-{year}-{month}-truncated.xlsx`.

### Service change

`fdp_app.admin.service.build_xlsx` gains `truncated: bool = False`.

When `truncated` is True, the sheet layout shifts by one row:

- Row 1: merged banner cell spanning all columns, text `"AVVISO: risultati troncati a 500 righe. Restringere i filtri per dati completi."`, styled bold with a yellow fill.
- Row 2: column headers.
- Row 3+: data.

When `truncated` is False, layout is unchanged from today (row 1 headers, row 2+ data).

### Template change

`fdp_app/templates/admin/history.html`: above the `{% if rows %}` block, render a Bootstrap alert when `truncated` is true:

```html
{% if truncated %}
<div class="alert alert-warning">
    <i class="bi bi-exclamation-triangle"></i>
    Risultati troncati a {{ max_rows }} righe. Restringere i filtri per dati completi.
</div>
{% endif %}
```

## Data flow

```
GET /admin/history?year=2026&month=5
  → routes.history()
  → PathTrackRepo.list_for_sub_cdc(sub_cdc_id=..., year=2026, month=5, limit=500)
  → SQL: SELECT TOP (501) pt.*, e.* FROM ... WHERE ... ORDER BY ...
  ← cursor returns ≤501 rows
  → truncated = len(rows) > 500
  → rows = rows[:500]
  → render_template("admin/history.html", rows=rows, truncated=truncated, max_rows=500, ...)
```

```
GET /admin/export?year=2026&month=5
  → routes.export()
  → PathTrackRepo.list_for_sub_cdc(..., limit=500)
  ← ≤501 rows
  → truncated = len(rows) > 500
  → rows = rows[:500]
  → build_xlsx(rows, year=2026, month=5, month_name="Maggio", truncated=truncated)
  → filename = "fogli-di-percorso-2026-05.xlsx" or "...-truncated.xlsx"
  → Response(xlsx_bytes, headers={"Content-Disposition": ...})
```

## Edge cases

| Case | Behavior |
|---|---|
| 0 rows | Not truncated. Existing empty-state message renders. |
| 1–500 rows | Not truncated. Layout unchanged. |
| Exactly 500 rows | Fetch returns 500 (≤501), `len(rows) > 500` is False. **Not truncated.** Correct — we asked for 501 and got fewer. |
| Exactly 501 rows | Fetch returns 501, slice to 500, `truncated=True`. Correct. |
| 1000+ rows | DB still only returns 501 (TOP clause). Slice to 500, `truncated=True`. |
| `limit=None` (legacy callers) | No `TOP` clause. Backward compatible. |

## Wording (Italian, matching existing UI)

- Template banner: `"Risultati troncati a 500 righe. Restringere i filtri per dati completi."`
- XLSX banner row: `"AVVISO: risultati troncati a 500 righe. Restringere i filtri per dati completi."`
- Filename suffix: `-truncated` (English — filename, not user-facing copy)

## Testing approach

### `tests/test_admin_routes.py` — new tests

1. `test_history_passes_limit_to_repo` — assert `list_for_sub_cdc` called with `limit=500`.
2. `test_history_shows_warning_when_truncated` — patch `MAX_HISTORY_ROWS` to 2, mock repo returns 3 rows, assert response contains `"Risultati troncati"`.
3. `test_history_no_warning_when_under_cap` — repo returns 1 row, assert response does NOT contain `"troncati"`.

### `tests/test_admin_export.py` — new tests

1. `test_export_passes_limit_to_repo` — assert `list_for_sub_cdc` called with `limit=500`.
2. `test_export_filename_has_truncated_suffix_when_capped` — patch `MAX_HISTORY_ROWS` to 2, mock repo returns 3 rows, assert `Content-Disposition` contains `fogli-di-percorso-2026-04-truncated.xlsx`.
3. `test_export_filename_unchanged_when_under_cap` — assert no `-truncated` in filename.
4. `test_build_xlsx_injects_banner_when_truncated` — call `build_xlsx(entries, ..., truncated=True)`, load workbook, assert row 1 cell contains `"AVVISO"` and `"troncati"`, assert headers shifted to row 2.
5. `test_build_xlsx_no_banner_when_not_truncated` — default `truncated=False`, layout unchanged (header row 1, data row 2). This is the existing behavior — covered by the current `test_build_xlsx_generates_valid_workbook`, no new test needed; verify it still passes.

### Existing tests to verify still pass

- `test_history_lists_rows` — should pass unchanged (1 row, not truncated, no warning).
- `test_build_xlsx_generates_valid_workbook` — should pass unchanged (truncated defaults to False).
- `test_build_xlsx_handles_empty_rows` — should pass unchanged.
- `test_export_returns_xlsx_with_correct_filename` — should pass unchanged (0 rows, not truncated).

## Files changed

| File | Change type |
|---|---|
| `fdp_app/repos/pathtrack_repo.py` | Add `limit` kwarg + `/*TOP*/` template marker |
| `fdp_app/admin/routes.py` | Add `MAX_HISTORY_ROWS`; pass `limit`; compute `truncated`; suffix filename |
| `fdp_app/admin/service.py` | Add `truncated` kwarg to `build_xlsx`; inject banner row |
| `fdp_app/templates/admin/history.html` | Render `alert-warning` when `truncated` |
| `tests/test_admin_routes.py` | 3 new tests |
| `tests/test_admin_export.py` | 4 new tests |
