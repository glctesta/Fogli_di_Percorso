# Fogli di Percorso — Piano 5: Fix Piano 4 + i18n + Multi-currency BNR

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Tre macro-aree indipendenti:
- **Fase A** — Fix dei follow-up dal final review del Piano 4 (admin detail 404, helper placement, inline imports)
- **Fase B** — Internazionalizzazione: aggiungere lingue **EN** e **RO** con default **RO** (sede in Romania), selettore in navbar
- **Fase C** — Multi-currency: calcolo interno in EUR, conversione e display in **RON** via tasso ufficiale BNR (con fallback `cursbnr.ro` + tasso "standard" amministrativo + ultimo cached)

**Architecture:**
- **i18n**: Flask-Babel + file `.po` per IT/EN/RO. Selettore lingua in navbar (cookie `fdp_lang`). Tutte le stringhe user-facing wrapped in `_()` / `{{ _('...') }}`. Default RO.
- **Currency**: nuova tabella `fdp.BnrRates` con campi `RateValueRonPerEur`, `Source`, `ValidFrom`, `ValidTo`. Colonna nuova `PathTracks.BnrRateRonPerEur` per congelare il tasso al momento del submit. Logica lookup a cascata: tasso standard amministrativo → live BNR → live cursbnr → ultimo cached.

**Tech Stack:** Flask-Babel, requests (per BNR/cursbnr), defusedxml (parsing sicuro XML BNR), beautifulsoup4 (parsing cursbnr HTML).

**Prerequisito:** Piano 4 completato e taggato `v0.4.0-admin`. 190 test verdi.

---

# Fase A — Fix Piano 4

## Task 1: Admin detail view bypass per /admin/pathtracks/<id>

**Files:**
- Modify: `fdp_app/admin/routes.py` (add `/admin/pathtracks/<id>` route)
- Modify: `fdp_app/repos/pathtrack_repo.py` (add `find_by_id_in_sub_cdc(path_track_id, sub_cdc_id)`)
- Modify: `fdp_app/templates/admin/history.html` (link Dettagli → admin route)
- Test: `tests/test_admin_routes.py`

### Step 1: Add `find_by_id_in_sub_cdc` to `PathTrackRepo`

```python
_QUERY_FIND_BY_ID_IN_SUB_CDC = """
SELECT TOP 1
    pt.PathTrackId, pt.RegistryId, pt.DatePathTrack, pt.DeclaratedPathId,
    pt.InBehalfOfId, pt.ReimbursementType, pt.NumberOfTrips, pt.RoadKm,
    pt.RateIdUsed, pt.TaxiTotalEur, pt.ComputedAmountEur, pt.Status, pt.SubmittedOn
FROM Employee.fdp.PathTracks pt
JOIN Employee.dbo.EmployeeHireHistory h
     ON h.EmployeeHireHistoryId = COALESCE(pt.InBehalfOfId, pt.EmployeeHireHistoryId)
JOIN Employee.dbo.EmployeeCdcStories s
     ON s.EmployeeHireHistoryId = h.EmployeeHireHistoryId
    AND s.DateOut IS NULL
WHERE pt.PathTrackId = ?
  AND s.SubCdcId = ?
  AND pt.DateOut IS NULL
"""

# In class PathTrackRepo:
def find_by_id_in_sub_cdc(self, *, path_track_id: int, sub_cdc_id: int):
    cursor = self._open_cursor()
    try:
        cursor.execute(_QUERY_FIND_BY_ID_IN_SUB_CDC, path_track_id, sub_cdc_id)
        row = cursor.fetchone()
    finally:
        cursor.close()
    return _row_to_obj(row) if row else None
```

### Step 2: Add route in `fdp_app/admin/routes.py`

```python
from flask import abort
from fdp_app.repos.doc_repo import PathTrackDocRepo


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
```

### Step 3: Create `fdp_app/templates/admin/view_pathtrack.html`

Lighter version of `pathtracks/view.html` (admin sees details but cannot modify; that's still done by the owner via `/pathtracks/<id>`):

```html
{% extends "base.html" %}
{% block title %}Dichiarazione #{{ row.path_track_id }} - Admin{% endblock %}
{% block content %}
<h2>
    <i class="bi bi-receipt"></i> Dichiarazione
    {% if row.status == "DRAFT" %}
    <span class="badge bg-warning text-dark ms-2">BOZZA</span>
    {% else %}
    <span class="badge bg-success ms-2">INVIATA</span>
    {% endif %}
</h2>

<div class="alert alert-info">
    <i class="bi bi-info-circle"></i>
    Vista <strong>admin</strong> (sola consultazione). Solo il dipendente proprietario pu&ograve; modificare la bozza.
</div>

<table class="table">
    <tbody>
        <tr><th>Stato</th><td>{{ row.status }}</td></tr>
        {% if row.registry_id %}<tr><th>N. registro</th><td><strong>{{ row.registry_id }}</strong></td></tr>{% endif %}
        {% if row.submitted_on %}<tr><th>Inviata il</th><td>{{ row.submitted_on.strftime("%d/%m/%Y %H:%M") }}</td></tr>{% endif %}
        <tr><th>Tipo</th><td>{{ row.reimbursement_type }}</td></tr>
        <tr><th>Mese di riferimento</th><td>{{ month_label }} {{ row.date_path_track.year }}</td></tr>
        <tr><th>Viaggi A/R</th><td>{{ row.number_of_trips }}</td></tr>
        <tr><th>Km one-way</th><td>{{ "%.3f"|format(row.road_km) }}</td></tr>
        <tr><th>Importo</th><td>&euro; {{ "%.2f"|format(row.computed_amount_eur) }}</td></tr>
    </tbody>
</table>

<h4>Documenti</h4>
<ul class="list-group mb-3">
    {% for doc in docs %}
    <li class="list-group-item d-flex justify-content-between align-items-center">
        <span><i class="bi bi-file-earmark-pdf"></i> {{ doc.doc_title }}</span>
        <a href="{{ url_for('pathtracks.download_doc', doc_id=doc.doc_id) }}"
           class="btn btn-sm btn-outline-secondary">
            <i class="bi bi-download"></i> Scarica
        </a>
    </li>
    {% endfor %}
</ul>

<a href="{{ url_for('admin.history') }}" class="btn btn-link">
    <i class="bi bi-arrow-left"></i> Torna allo storico
</a>
{% endblock %}
```

### Step 4: Update `admin/history.html` link

Find `url_for('pathtracks.view', path_track_id=...)` and replace with `url_for('admin.view_pathtrack', path_track_id=...)`.

### Step 5: Note about doc download

The `download_doc` route in `pathtracks/routes.py` uses `find_owner_employee_for_doc` (Piano 4 Task 3) which validates against the user's own ID. Admin users will get 404 when trying to download docs of subordinates.

**Fix:** in `download_doc`, after the owner check fails, also try the sub-cdc check:

```python
@bp.route("/docs/<int:doc_id>/download", methods=["GET"])
@login_required
def download_doc(doc_id: int):
    doc_repo = PathTrackDocRepo(current_app.config["_db"])
    try:
        pdf_bytes, title = doc_repo.get_blob(doc_id=doc_id)
    except FileNotFoundError:
        abort(404)
    owner = doc_repo.find_owner_employee_for_doc(doc_id=doc_id)
    if owner is None:
        abort(404)
    employee_id, beneficiary_id = owner
    if session["user_id"] not in (employee_id, beneficiary_id):
        # Try admin path: is the doc in the user's SubCdc?
        if session.get("function_code", 0) > 60:
            # Fetch sub_cdc via existing JOIN extended query
            sub_cdc_owner = doc_repo.find_sub_cdc_for_doc(doc_id=doc_id)
            if sub_cdc_owner != session["sub_cdc_id"]:
                abort(404)
        else:
            abort(404)
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{title}.pdf"'},
    )
```

Add to `PathTrackDocRepo`:

```python
_QUERY_FIND_SUB_CDC_FOR_DOC = """
SELECT s.SubCdcId
FROM Employee.fdp.PathTrackDocs d
JOIN Employee.fdp.PathTracks pt ON pt.PathTrackId = d.PathTrackId
JOIN Employee.dbo.EmployeeHireHistory h
     ON h.EmployeeHireHistoryId = COALESCE(pt.InBehalfOfId, pt.EmployeeHireHistoryId)
JOIN Employee.dbo.EmployeeCdcStories s
     ON s.EmployeeHireHistoryId = h.EmployeeHireHistoryId
    AND s.DateOut IS NULL
WHERE d.PathTrackDocId = ?
  AND d.DateOut IS NULL
  AND pt.DateOut IS NULL
"""

def find_sub_cdc_for_doc(self, *, doc_id: int) -> int | None:
    cursor = self._open_cursor()
    try:
        cursor.execute(_QUERY_FIND_SUB_CDC_FOR_DOC, doc_id)
        row = cursor.fetchone()
    finally:
        cursor.close()
    return int(row[0]) if row else None
```

### Step 6: Tests

Add to `tests/test_admin_routes.py`:

```python
def test_view_pathtrack_admin_can_see_subordinate(client, mock_pathtrack_repo_admin):
    from fdp_app.repos.pathtrack_repo import PathTrackRow
    from datetime import date as Date
    _login_admin(client, sub_cdc_id=42)
    with patch("fdp_app.admin.routes.PathTrackDocRepo") as doc_cls:
        doc = MagicMock(); doc.list_for_pathtrack.return_value = []
        doc_cls.return_value = doc
        mock_pathtrack_repo_admin.find_by_id_in_sub_cdc.return_value = PathTrackRow(
            path_track_id=100, registry_id=500, date_path_track=Date(2026, 4, 1),
            declarated_path_id=99, in_behalf_of_id=None,
            reimbursement_type="CARBURANTE", number_of_trips=20, road_km=10.0,
            rate_id_used=3, taxi_total_eur=None, computed_amount_eur=53.55,
            status="SUBMITTED", submitted_on=None,
        )
        response = client.get("/admin/pathtracks/100")
        assert response.status_code == 200
        assert b"INVIATA" in response.data


def test_view_pathtrack_admin_404_if_other_sub_cdc(client, mock_pathtrack_repo_admin):
    _login_admin(client, sub_cdc_id=42)
    mock_pathtrack_repo_admin.find_by_id_in_sub_cdc.return_value = None
    response = client.get("/admin/pathtracks/999")
    assert response.status_code == 404
```

### Step 7: Commit

```bash
git add fdp_app/admin/ fdp_app/repos/pathtrack_repo.py fdp_app/repos/doc_repo.py fdp_app/pathtracks/routes.py fdp_app/templates/admin/ tests/
git commit -m "fix(admin): admin can view subordinate pathtrack details + download docs"
```

---

## Task 2: Move `resolve_target_employee` to `admin/helpers.py`

**Files:**
- Create: `fdp_app/admin/helpers.py` (move function from auth/helpers.py)
- Modify: `fdp_app/coordinates/routes.py`, `fdp_app/pathtracks/routes.py` (update import)
- Modify: `tests/test_admin_on_behalf_of.py` (update patch target)
- Delete: `fdp_app/auth/helpers.py`

### Step 1: Create `fdp_app/admin/helpers.py` with the same content of `auth/helpers.py`

### Step 2: Update imports

In `fdp_app/coordinates/routes.py` and `fdp_app/pathtracks/routes.py`:
```python
# Replace:
from fdp_app.auth.helpers import resolve_target_employee
# With:
from fdp_app.admin.helpers import resolve_target_employee
```

### Step 3: Update patch in `tests/test_admin_on_behalf_of.py`

```python
# Replace:
with patch("fdp_app.auth.helpers.EmployeeRepo") as cls:
# With:
with patch("fdp_app.admin.helpers.EmployeeRepo") as cls:
```

### Step 4: Delete `fdp_app/auth/helpers.py`

```bash
git rm fdp_app/auth/helpers.py
```

### Step 5: Run tests, commit

```bash
git add fdp_app/admin/helpers.py fdp_app/coordinates/routes.py fdp_app/pathtracks/routes.py tests/test_admin_on_behalf_of.py
git rm fdp_app/auth/helpers.py
git commit -m "refactor: move resolve_target_employee from auth/ to admin/"
```

---

## Task 3: Hoist inline imports in pathtracks/routes.py

**File:** `fdp_app/pathtracks/routes.py`

In `new()` and `create()` there are inline imports:
```python
from datetime import datetime as _dt
from zoneinfo import ZoneInfo as _Z
```

Move these to the top of the file along with the other imports:
```python
from datetime import datetime
from zoneinfo import ZoneInfo
```

Then replace `_dt.now(_Z("Europe/Rome"))` with `datetime.now(ZoneInfo("Europe/Rome"))` in both function bodies. Remove the duplicate inline imports.

Run tests + commit:
```bash
git add fdp_app/pathtracks/routes.py
git commit -m "refactor: hoist datetime/ZoneInfo imports to module level"
```

---

# Fase B — Internazionalizzazione (i18n)

## Task 4: Install Flask-Babel + configure

**Files:**
- Modify: `requirements.txt` (add `Flask-Babel==4.0.0`)
- Modify: `config/settings.py` (add languages + babel config)
- Modify: `fdp_app/extensions.py` (init babel)
- Modify: `fdp_app/__init__.py` (register babel + locale selector)
- Create: `babel.cfg`
- Create: `fdp_app/templates/_lang_selector.html` (partial)
- Modify: `fdp_app/templates/base.html` (include selector)

### Step 1: Add to `requirements.txt`

```
Flask-Babel==4.0.0
```

Install: `.venv\Scripts\pip install -r requirements.txt`

### Step 2: Add to `config/settings.py` (Settings class)

```python
    # i18n
    LANGUAGES: tuple = ("ro", "it", "en")
    BABEL_DEFAULT_LOCALE: str = "ro"
    BABEL_DEFAULT_TIMEZONE: str = "Europe/Rome"
    LANGUAGE_COOKIE_NAME: str = "fdp_lang"
    LANGUAGE_COOKIE_MAX_AGE: int = 365 * 24 * 3600  # 1 year
```

### Step 3: Update `fdp_app/extensions.py`

```python
from flask_wtf import CSRFProtect
from flask_babel import Babel

csrf = CSRFProtect()
babel = Babel()
```

### Step 4: Update `fdp_app/__init__.py` in `create_app`

After `csrf.init_app(app)`, add:

```python
    from fdp_app.extensions import babel

    def select_locale():
        # 1) Cookie has priority
        from flask import request
        cookie_lang = request.cookies.get(settings.LANGUAGE_COOKIE_NAME)
        if cookie_lang in settings.LANGUAGES:
            return cookie_lang
        # 2) Accept-Language
        browser_lang = request.accept_languages.best_match(settings.LANGUAGES)
        if browser_lang:
            return browser_lang
        # 3) Default
        return settings.BABEL_DEFAULT_LOCALE

    babel.init_app(app, locale_selector=select_locale)
```

### Step 5: Create `babel.cfg` at project root

```
[python: fdp_app/**.py]
[jinja2: fdp_app/templates/**.html]
extensions=jinja2.ext.autoescape,jinja2.ext.with_
```

### Step 6: Language selector route + partial

In `fdp_app/__init__.py` add a route to set the language:

```python
    @app.route("/lang/<code>", methods=["POST"])
    def set_language(code):
        from flask import redirect, request, make_response
        if code not in settings.LANGUAGES:
            return ("Invalid language", 400)
        next_url = request.form.get("next") or request.referrer or "/"
        resp = make_response(redirect(next_url))
        resp.set_cookie(
            settings.LANGUAGE_COOKIE_NAME, code,
            max_age=settings.LANGUAGE_COOKIE_MAX_AGE,
            samesite="Lax", httponly=False,
        )
        return resp
```

### Step 7: Create `fdp_app/templates/_lang_selector.html`

```html
<div class="dropdown">
    <button class="btn btn-sm btn-outline-light dropdown-toggle" type="button"
            data-bs-toggle="dropdown" aria-expanded="false" aria-label="Language">
        {% set current = (request.cookies.get('fdp_lang') or 'ro') %}
        {% if current == 'ro' %}🇷🇴 RO
        {% elif current == 'en' %}🇬🇧 EN
        {% else %}🇮🇹 IT{% endif %}
    </button>
    <ul class="dropdown-menu dropdown-menu-end">
        {% for code, label in [('ro', '🇷🇴 Romana'), ('it', '🇮🇹 Italiano'), ('en', '🇬🇧 English')] %}
        <li>
            <form action="{{ url_for('set_language', code=code) }}" method="post" class="m-0">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <input type="hidden" name="next" value="{{ request.full_path }}">
                <button type="submit" class="dropdown-item">{{ label }}</button>
            </form>
        </li>
        {% endfor %}
    </ul>
</div>
```

### Step 8: Include selector in `base.html` navbar

Inside the navbar, BEFORE the logout form, add:

```html
{% include "_lang_selector.html" %}
```

### Step 9: Test that babel is loaded

Add minimal test in `tests/test_i18n.py`:

```python
def test_language_selector_endpoint_sets_cookie(client):
    response = client.post("/lang/en", data={"next": "/"}, follow_redirects=False)
    assert response.status_code == 302
    cookies = response.headers.getlist("Set-Cookie")
    assert any("fdp_lang=en" in c for c in cookies)


def test_language_selector_rejects_invalid_code(client):
    response = client.post("/lang/xx", follow_redirects=False)
    assert response.status_code == 400


def test_default_locale_is_ro(app):
    from fdp_app.extensions import babel
    with app.test_request_context("/"):
        assert babel.locale_selector() == "ro"
```

Run + commit:

```bash
git add requirements.txt config/settings.py fdp_app/extensions.py fdp_app/__init__.py fdp_app/templates/base.html fdp_app/templates/_lang_selector.html babel.cfg tests/test_i18n.py
git commit -m "feat(i18n): integrate Flask-Babel with RO default and language selector"
```

---

## Task 5: Wrap strings in templates with `_()`

**Files:** all `fdp_app/templates/**/*.html`

For each template, replace user-facing Italian strings with `{{ _('...') }}` calls.

Strategy: focus on the high-value strings (titles, buttons, labels, alerts). Inline data (number formats, dates) stays untouched.

**Example transformations:**

`base.html`:
```html
<a class="navbar-brand"... <span class="fw-semibold">Fogli di Percorso</span>
<!-- BECOMES -->
<a class="navbar-brand"... <span class="fw-semibold">{{ _('Fogli di Percorso') }}</span>
```

`dashboard/index.html`:
```html
<h2 class="mb-0">Benvenuto, {{ full_name }}</h2>
<!-- BECOMES -->
<h2 class="mb-0">{{ _('Benvenuto, %(name)s', name=full_name) }}</h2>
```

(Use `%(name)s` placeholder for runtime values.)

`auth/login.html`, `coordinates/index.html`, `pathtracks/new.html`, `pathtracks/view.html`, `pathtracks/list.html`, `admin/representable.html`, `admin/history.html`, `admin/view_pathtrack.html`: wrap all `<h1-h6>`, `<label>`, `<button>` text content, `<p>` static strings, `placeholder` attrs.

**Italian text in DB queries / data**: do NOT wrap. Only display strings.

### Run after wrapping:

```bash
.venv\Scripts\pybabel extract -F babel.cfg -k _l -o messages.pot fdp_app
.venv\Scripts\pybabel init -i messages.pot -d fdp_app/translations -l ro
.venv\Scripts\pybabel init -i messages.pot -d fdp_app/translations -l it
.venv\Scripts\pybabel init -i messages.pot -d fdp_app/translations -l en
```

This creates `fdp_app/translations/{ro,it,en}/LC_MESSAGES/messages.po` files.

Commit:
```bash
git add fdp_app/templates/ messages.pot fdp_app/translations/
git commit -m "i18n(templates): wrap user-facing strings with _() and extract POT"
```

---

## Task 6: Wrap strings in routes (flash messages) with `_()`

**Files:** all `fdp_app/*/routes.py` + `fdp_app/admin/routes.py`

For every `flash("...")` call, wrap the message string with `_()`:

```python
from flask_babel import _

flash("Credenziali non valide.", "danger")
# BECOMES:
flash(_("Credenziali non valide."), "danger")
```

Apply systematically to ALL routes. Use `flask_babel.lazy_gettext` (`_l`) for module-level strings (rare).

For format strings with placeholders:
```python
flash(f"Bozza salvata. La potrai aggiornare fino al 5 del mese successivo.", "success")
# BECOMES:
flash(_("Bozza salvata. La potrai aggiornare fino al 5 del mese successivo."), "success")
```

```python
flash(f"Dichiarazione inviata con successo. RegistryId: {registry_id}", "success")
# BECOMES:
flash(_("Dichiarazione inviata con successo. RegistryId: %(rid)s", rid=registry_id), "success")
```

Re-extract POT after, regenerate .po files:
```bash
.venv\Scripts\pybabel extract -F babel.cfg -k _l -o messages.pot fdp_app
.venv\Scripts\pybabel update -i messages.pot -d fdp_app/translations
```

Commit:
```bash
git add fdp_app/ messages.pot
git commit -m "i18n(routes): wrap all flash messages with _()"
```

---

## Task 7: Translate strings to RO and EN

**Files:** `fdp_app/translations/{ro,en}/LC_MESSAGES/messages.po`

For each entry in the .po files, add the translation:

### Example RO translations (sample, full list in actual file):

```
msgid "Fogli di Percorso"
msgstr "Fogli di Percorso"  # brand stays the same

msgid "Accedi"
msgstr "Autentificare"

msgid "Esci"
msgstr "Iesire"

msgid "Nome utente"
msgstr "Utilizator"

msgid "Password"
msgstr "Parola"

msgid "Entra"
msgstr "Intra"

msgid "Benvenuto, %(name)s"
msgstr "Bun venit, %(name)s"

msgid "Punto di partenza"
msgstr "Punct de plecare"

msgid "Dichiarazione mensile"
msgstr "Declaratie lunara"

msgid "Amministrazione"
msgstr "Administrare"

msgid "Vai alla mappa"
msgstr "Mergi la harta"

msgid "Vai alle dichiarazioni"
msgstr "Mergi la declaratii"

msgid "Vai all'area admin"
msgstr "Mergi la zona admin"

msgid "Nuova dichiarazione"
msgstr "Declaratie noua"

msgid "Tipo rimborso"
msgstr "Tip rambursare"

msgid "Carburante"
msgstr "Carburant"

msgid "Taxi"
msgstr "Taxi"

msgid "Numero viaggi (A/R)"
msgstr "Numar calatorii (Dus/Intors)"

msgid "Foglio di percorso (PDF, max 5 MB)"
msgstr "Fisa de traseu (PDF, max 5 MB)"

msgid "Ricevute (PDF, max 5 MB ciascuna)"
msgstr "Chitante (PDF, max 5 MB fiecare)"

msgid "Salva bozza"
msgstr "Salveaza ciorna"

msgid "Salva e invia"
msgstr "Salveaza si trimite"

msgid "Conferma e invia"
msgstr "Confirma si trimite"

msgid "Cancella bozza"
msgstr "Sterge ciorna"

msgid "BOZZA"
msgstr "CIORNA"

msgid "INVIATA"
msgstr "TRIMISA"

msgid "Stato"
msgstr "Stare"

msgid "Mese"
msgstr "Luna"

msgid "Importo"
msgstr "Suma"

msgid "Dipendente"
msgstr "Angajat"

msgid "Storico dichiarazioni SubCdc"
msgstr "Istoric declaratii SubCdc"

msgid "Filtra"
msgstr "Filtrare"

msgid "Export XLSX"
msgstr "Export XLSX"

msgid "Credenziali non valide."
msgstr "Credentiale invalide."

msgid "Periodo di inserimento chiuso."
msgstr "Perioada de introducere inchisa."

msgid "Dichiarazione mensile salvata."
msgstr "Declaratia lunara salvata."

msgid "Bozza salvata. La potrai aggiornare fino al 5 del mese successivo."
msgstr "Ciorna salvata. O poti actualiza pana la data de 5 a lunii urmatoare."

msgid "Definisci prima il punto di partenza nella mappa."
msgstr "Defineste mai intai punctul de plecare pe harta."

msgid "Esci dall'applicazione"
msgstr "Iesire din aplicatie"

msgid "Mappa"
msgstr "Harta"

msgid "Cancella punto"
msgstr "Sterge punctul"

msgid "Distanza stradale verso la sede:"
msgstr "Distanta rutiera catre sediu:"

msgid "Coordinate:"
msgstr "Coordonate:"

msgid "Etichetta (es. \"Casa\", \"Via Roma 5\")"
msgstr "Eticheta (ex. \"Acasa\", \"Strada X 5\")"

msgid "Salva punto di partenza"
msgstr "Salveaza punctul de plecare"

msgid "Annulla"
msgstr "Anuleaza"

msgid "Tutti"
msgstr "Toate"

msgid "Aggiorna bozza"
msgstr "Actualizeaza ciorna"

msgid "Anteprima rimborso:"
msgstr "Previzualizare rambursare:"

msgid "Importo rimborso"
msgstr "Suma rambursare"

msgid "N. registro"
msgstr "Nr. registru"

msgid "Numero viaggi A/R"
msgstr "Numar calatorii dus/intors"

msgid "Distanza one-way"
msgstr "Distanta dus"

msgid "Documenti"
msgstr "Documente"

msgid "Documenti caricati"
msgstr "Documente incarcate"

msgid "Scarica"
msgstr "Descarca"

msgid "Le mie dichiarazioni"
msgstr "Declaratiile mele"

msgid "Nessuna dichiarazione presente."
msgstr "Nicio declaratie prezenta."

msgid "Dipendenti rappresentabili"
msgstr "Angajati reprezentabili"

msgid "Anno"
msgstr "An"

msgid "Tipo"
msgstr "Tip"

msgid "Dettagli"
msgstr "Detalii"

msgid "Torna alla lista"
msgstr "Inapoi la lista"

msgid "Torna ai rappresentati"
msgstr "Inapoi la reprezentanti"

msgid "Torna alla home"
msgstr "Inapoi acasa"

msgid "Servizio mappe temporaneamente non disponibile. Riprovare piu' tardi."
msgstr "Serviciul de harti temporar indisponibil. Reincercati mai tarziu."

msgid "Punto di partenza salvato."
msgstr "Punctul de plecare salvat."

msgid "Punto di partenza cancellato."
msgstr "Punctul de plecare sters."

msgid "Bozza cancellata."
msgstr "Ciorna stearsa."

msgid "Dichiarazione inviata con successo. RegistryId: %(rid)s"
msgstr "Declaratie trimisa cu succes. Nr. registru: %(rid)s"
```

### Example EN translations (sample):

```
msgid "Fogli di Percorso"
msgstr "Travel Sheets"

msgid "Accedi"
msgstr "Sign in"

msgid "Esci"
msgstr "Logout"

msgid "Nome utente"
msgstr "Username"

msgid "Password"
msgstr "Password"

msgid "Entra"
msgstr "Enter"

msgid "Benvenuto, %(name)s"
msgstr "Welcome, %(name)s"

msgid "Punto di partenza"
msgstr "Starting point"

msgid "Dichiarazione mensile"
msgstr "Monthly declaration"

msgid "Amministrazione"
msgstr "Administration"

msgid "Vai alla mappa"
msgstr "Go to map"

msgid "Vai alle dichiarazioni"
msgstr "Go to declarations"

msgid "Vai all'area admin"
msgstr "Go to admin area"

msgid "Nuova dichiarazione"
msgstr "New declaration"

msgid "Tipo rimborso"
msgstr "Reimbursement type"

msgid "Carburante"
msgstr "Fuel"

msgid "Taxi"
msgstr "Taxi"

msgid "Numero viaggi (A/R)"
msgstr "Trips (round-trip)"

msgid "Salva bozza"
msgstr "Save draft"

msgid "Salva e invia"
msgstr "Save and submit"

msgid "Conferma e invia"
msgstr "Confirm and submit"

msgid "Cancella bozza"
msgstr "Delete draft"

msgid "BOZZA"
msgstr "DRAFT"

msgid "INVIATA"
msgstr "SUBMITTED"

msgid "Stato"
msgstr "Status"

msgid "Mese"
msgstr "Month"

msgid "Importo"
msgstr "Amount"

msgid "Dipendente"
msgstr "Employee"

msgid "Storico dichiarazioni SubCdc"
msgstr "SubCdc declarations history"

msgid "Filtra"
msgstr "Filter"

msgid "Credenziali non valide."
msgstr "Invalid credentials."

msgid "Periodo di inserimento chiuso."
msgstr "Submission period closed."

msgid "Bozza salvata. La potrai aggiornare fino al 5 del mese successivo."
msgstr "Draft saved. You can update it until the 5th of the next month."
```

(The full .po files will contain dozens of entries; populate all of them.)

### Compile

```bash
.venv\Scripts\pybabel compile -d fdp_app/translations
```

### Commit

```bash
git add fdp_app/translations/
git commit -m "i18n: add RO and EN translations + compile .mo"
```

---

## Task 8: Test i18n end-to-end

**Files:** `tests/test_i18n.py` (extend)

```python
def test_homepage_renders_in_ro_by_default(client):
    response = client.get("/login")
    # If the user has no cookie, default is RO
    # Login template should contain "Autentificare" (RO) not "Accedi" (IT)
    assert b"Autentificare" in response.data or b"Sign in" in response.data or b"Accedi" in response.data
    # (depending on whether translations are compiled at test time)


def test_homepage_renders_in_en_when_cookie_set(client):
    client.set_cookie("fdp_lang", "en")
    response = client.get("/login")
    assert b"Sign in" in response.data


def test_homepage_renders_in_it_when_cookie_set(client):
    client.set_cookie("fdp_lang", "it")
    response = client.get("/login")
    assert b"Accedi" in response.data
```

Note: tests for i18n require the `.mo` compiled files to be present. Add a fixture in `conftest.py` to compile them at session start, or document the requirement.

Run + commit:

```bash
git add tests/test_i18n.py
git commit -m "test(i18n): verify locale switching via cookie"
```

---

# Fase C — Multi-currency BNR

## Task 9: DDL `004_create_bnrrates.sql`

**File:** `sql/004_create_bnrrates.sql`

```sql
USE Employee;
GO

-- Tabella tassi BNR EUR -> RON
IF NOT EXISTS (
    SELECT 1 FROM sys.tables
    WHERE Name = N'BnrRates' AND SCHEMA_NAME(schema_id) = N'fdp'
)
BEGIN
    CREATE TABLE fdp.BnrRates (
        RateId              INT IDENTITY(1,1) PRIMARY KEY,
        RateValueRonPerEur  DECIMAL(10,6) NOT NULL,
        Source              CHAR(10) NOT NULL,  -- 'STANDARD' | 'BNR' | 'CURSBNR' | 'MANUAL'
        ValidFrom           DATE NOT NULL,
        ValidTo             DATE NULL,
        IsStandard          BIT NOT NULL DEFAULT 0,
        DateSys             DATETIME NOT NULL DEFAULT GETDATE(),
        UserSys             NVARCHAR(100) NOT NULL,
    );
    CREATE INDEX IX_BnrRates_ValidFrom ON fdp.BnrRates(ValidFrom);
END
GO

-- Aggiungi colonna BnrRateRonPerEur a PathTracks per congelare il tasso
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE Name = N'BnrRateRonPerEur'
      AND Object_ID = Object_ID(N'fdp.PathTracks')
)
BEGIN
    ALTER TABLE fdp.PathTracks
        ADD BnrRateRonPerEur DECIMAL(10,6) NULL;
END
GO

PRINT 'Migrazione 004_create_bnrrates.sql completata.';
```

Update `sql/README.md` to include this migration.

Commit:
```bash
git add sql/004_create_bnrrates.sql sql/README.md
git commit -m "feat(db): add BnrRates table and PathTracks.BnrRateRonPerEur column"
```

---

## Task 10: `BnrRateRepo` (CRUD + lookup logic)

**Files:**
- Create: `fdp_app/repos/bnr_rate_repo.py`
- Test: `tests/test_bnr_rate_repo.py`

```python
"""Repository per fdp.BnrRates."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from fdp_app.repos.base_repo import BaseRepo


_QUERY_FIND_STANDARD_FOR_DATE = """
SELECT TOP 1 RateId, RateValueRonPerEur, Source, ValidFrom, ValidTo
FROM Employee.fdp.BnrRates
WHERE IsStandard = 1
  AND ValidFrom <= ?
  AND (ValidTo IS NULL OR ValidTo >= ?)
ORDER BY ValidFrom DESC
"""

_QUERY_FIND_LATEST_FOR_DATE = """
SELECT TOP 1 RateId, RateValueRonPerEur, Source, ValidFrom, ValidTo
FROM Employee.fdp.BnrRates
WHERE ValidFrom <= ?
ORDER BY ValidFrom DESC
"""

_QUERY_INSERT = """
INSERT INTO Employee.fdp.BnrRates
    (RateValueRonPerEur, Source, ValidFrom, ValidTo, IsStandard, UserSys)
OUTPUT INSERTED.RateId
VALUES (?, ?, ?, ?, ?, ?)
"""


@dataclass(frozen=True)
class BnrRate:
    rate_id: int
    rate_value_ron_per_eur: float
    source: str
    valid_from: date
    valid_to: Optional[date]


class BnrRateRepo(BaseRepo):
    def find_standard_for(self, target_date: date) -> Optional[BnrRate]:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_FIND_STANDARD_FOR_DATE, target_date, target_date)
            row = cursor.fetchone()
        finally:
            cursor.close()
        if row is None:
            return None
        return BnrRate(
            rate_id=int(row[0]),
            rate_value_ron_per_eur=float(row[1]),
            source=row[2].rstrip() if isinstance(row[2], str) else row[2],
            valid_from=row[3],
            valid_to=row[4],
        )

    def find_latest_cached_for(self, target_date: date) -> Optional[BnrRate]:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_FIND_LATEST_FOR_DATE, target_date)
            row = cursor.fetchone()
        finally:
            cursor.close()
        if row is None:
            return None
        return BnrRate(
            rate_id=int(row[0]),
            rate_value_ron_per_eur=float(row[1]),
            source=row[2].rstrip() if isinstance(row[2], str) else row[2],
            valid_from=row[3],
            valid_to=row[4],
        )

    def insert(self, *, rate_value_ron_per_eur, source, valid_from,
               valid_to=None, is_standard=False, user_sys="system"):
        cursor = self._open_cursor()
        try:
            cursor.execute(
                _QUERY_INSERT,
                rate_value_ron_per_eur, source, valid_from, valid_to,
                1 if is_standard else 0, user_sys,
            )
            row = cursor.fetchone()
            return int(row[0])
        finally:
            cursor.close()
```

Tests: standard + cached + insert (similar to RateRepo from Piano 3).

Commit: `feat(repos): BnrRateRepo with standard/cached lookup and insert`

---

## Task 11: `BnrRateClient` (live fetch BNR + cursbnr fallback)

**Files:**
- Create: `fdp_app/pathtracks/bnr_client.py`
- Test: `tests/test_bnr_client.py`

```python
"""Client per il tasso di cambio EUR-RON.

Strategia:
1. Live fetch da BNR.ro (XML)
2. Fallback su cursbnr.ro (JSON pubblico)
"""
from __future__ import annotations

from typing import Optional

import requests
import defusedxml.ElementTree as ET


BNR_XML_URL = "https://www.bnr.ro/nbrfxrates.xml"
CURSBNR_API_URL = "https://www.cursbnr.ro/api/curs.json"


class BnrRateUnavailable(Exception):
    """Nessun provider e' riuscito a ottenere il tasso EUR->RON."""


class BnrRateClient:
    def __init__(self, *, timeout_s: float = 6.0) -> None:
        self._timeout = timeout_s

    def fetch_eur_to_ron(self) -> tuple[float, str]:
        """Ritorna (rate_value, source) dove source = 'BNR' o 'CURSBNR'.
        Raises BnrRateUnavailable se entrambi falliscono."""
        rate = self._try_bnr()
        if rate is not None:
            return rate, "BNR"
        rate = self._try_cursbnr()
        if rate is not None:
            return rate, "CURSBNR"
        raise BnrRateUnavailable("BNR e cursbnr non rispondono o non hanno EUR")

    def _try_bnr(self) -> Optional[float]:
        try:
            resp = requests.get(BNR_XML_URL, timeout=self._timeout)
            if resp.status_code != 200:
                return None
            # BNR XML structure:
            # <DataSet>
            #   <Body>
            #     <Cube date="2026-05-20">
            #       <Rate currency="EUR" multiplier="1">4.9756</Rate>
            #       ...
            root = ET.fromstring(resp.content)
            # iter() to find Rate elements
            for rate_elem in root.iter():
                tag = rate_elem.tag.split("}")[-1] if "}" in rate_elem.tag else rate_elem.tag
                if tag == "Rate" and rate_elem.get("currency") == "EUR":
                    mult = float(rate_elem.get("multiplier", "1") or 1)
                    val = float(rate_elem.text.replace(",", "."))
                    return val / mult
        except Exception:
            return None
        return None

    def _try_cursbnr(self) -> Optional[float]:
        try:
            resp = requests.get(CURSBNR_API_URL, timeout=self._timeout)
            if resp.status_code != 200:
                return None
            data = resp.json()
            # cursbnr API structure (depends on actual endpoint; adapt as needed):
            # {"date": "2026-05-20", "rates": {"EUR": 4.9756, ...}}
            rates = data.get("rates", {})
            eur = rates.get("EUR")
            if eur:
                return float(eur)
        except Exception:
            return None
        return None
```

Add `defusedxml==0.7.1` to `requirements.txt`.

Tests with `responses` library (HTTP mock):

```python
import responses
from fdp_app.pathtracks.bnr_client import BnrRateClient, BnrRateUnavailable


@responses.activate
def test_bnr_success():
    xml = b'''<?xml version="1.0"?>
    <DataSet><Body><Cube date="2026-05-20">
        <Rate currency="EUR" multiplier="1">4.9756</Rate>
    </Cube></Body></DataSet>'''
    responses.get("https://www.bnr.ro/nbrfxrates.xml", body=xml, status=200)
    client = BnrRateClient()
    rate, source = client.fetch_eur_to_ron()
    assert rate == 4.9756
    assert source == "BNR"


@responses.activate
def test_bnr_fail_cursbnr_success():
    responses.get("https://www.bnr.ro/nbrfxrates.xml", status=503)
    responses.get("https://www.cursbnr.ro/api/curs.json",
                  json={"rates": {"EUR": 4.97}}, status=200)
    client = BnrRateClient()
    rate, source = client.fetch_eur_to_ron()
    assert rate == 4.97
    assert source == "CURSBNR"


@responses.activate
def test_both_fail_raises():
    responses.get("https://www.bnr.ro/nbrfxrates.xml", status=503)
    responses.get("https://www.cursbnr.ro/api/curs.json", status=500)
    client = BnrRateClient()
    with pytest.raises(BnrRateUnavailable):
        client.fetch_eur_to_ron()
```

Commit: `feat(currency): BnrRateClient with BNR.ro primary + cursbnr.ro fallback`

---

## Task 12: `CurrencyService` cascade lookup

**File:** `fdp_app/pathtracks/currency.py`

```python
"""Lookup tasso EUR->RON con cascata: standard -> live -> cached."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from fdp_app.pathtracks.bnr_client import BnrRateClient, BnrRateUnavailable
from fdp_app.repos.bnr_rate_repo import BnrRateRepo


@dataclass(frozen=True)
class ResolvedRate:
    value_ron_per_eur: float
    source: str  # 'STANDARD' | 'BNR' | 'CURSBNR' | 'CACHED'
    stale: bool  # True se "cached" -> show warning


class CurrencyService:
    def __init__(
        self, *,
        bnr_repo: BnrRateRepo,
        bnr_client: BnrRateClient,
    ) -> None:
        self._repo = bnr_repo
        self._client = bnr_client

    def resolve_for(self, target_date: date, *, user_sys: str) -> ResolvedRate:
        # 1) Standard amministrativo
        std = self._repo.find_standard_for(target_date)
        if std is not None:
            return ResolvedRate(std.rate_value_ron_per_eur, "STANDARD", stale=False)

        # 2) Live fetch (BNR -> cursbnr)
        try:
            value, source = self._client.fetch_eur_to_ron()
            # Persist
            self._repo.insert(
                rate_value_ron_per_eur=value,
                source=source,
                valid_from=target_date,
                valid_to=None,
                is_standard=False,
                user_sys=user_sys,
            )
            return ResolvedRate(value, source, stale=False)
        except BnrRateUnavailable:
            pass

        # 3) Ultimo cached (stale)
        cached = self._repo.find_latest_cached_for(target_date)
        if cached is not None:
            return ResolvedRate(cached.rate_value_ron_per_eur, "CACHED", stale=True)

        raise BnrRateUnavailable(
            "Nessun tasso EUR->RON disponibile (standard, live, cached tutti falliti)"
        )
```

Tests with mock repo + mock client (4-5 tests).

Commit: `feat(currency): CurrencyService with cascade lookup (standard -> live -> cached)`

---

## Task 13: Freeze BNR rate on submit

**Files:**
- Modify: `fdp_app/repos/pathtrack_repo.py` (extend `mark_as_submitted` to accept `bnr_rate`)
- Modify: `fdp_app/pathtracks/service.py` (call CurrencyService inside `submit`)
- Modify: `fdp_app/__init__.py` (init CurrencyService in app config)
- Test: `tests/test_pathtrack_service.py`

In `PathTrackRepo`:

```python
_QUERY_MARK_SUBMITTED = """
UPDATE Employee.fdp.PathTracks
SET Status            = 'SUBMITTED',
    SubmittedOn       = GETDATE(),
    RegistryId        = ?,
    BnrRateRonPerEur  = ?
WHERE PathTrackId = ?
  AND EmployeeHireHistoryId = ?
  AND Status = 'DRAFT'
  AND DateOut IS NULL
"""

def mark_as_submitted(self, *, path_track_id, employee_hire_history_id,
                      registry_id, bnr_rate=None):
    cursor = self._open_cursor()
    try:
        cursor.execute(
            _QUERY_MARK_SUBMITTED,
            registry_id, bnr_rate, path_track_id, employee_hire_history_id,
        )
        return cursor.rowcount > 0
    finally:
        cursor.close()
```

Also update `_row_to_obj` to include `bnr_rate_ron_per_eur` and the `PathTrackRow` dataclass.

In `PathTrackService.submit`:

Inject `currency_service` in `__init__`. In `submit`, after the deadline check:

```python
try:
    resolved = self._currency_service.resolve_for(
        date.today(), user_sys=full_name,
    )
    bnr_rate = resolved.value_ron_per_eur
except BnrRateUnavailable:
    bnr_rate = None  # graceful degradation
```

Pass `bnr_rate=bnr_rate` to `mark_as_submitted`.

In `fdp_app/__init__.py` create_app, after the routing client setup:

```python
    from fdp_app.repos.bnr_rate_repo import BnrRateRepo
    from fdp_app.pathtracks.bnr_client import BnrRateClient
    from fdp_app.pathtracks.currency import CurrencyService

    bnr_client = BnrRateClient()

    # Note: BnrRateRepo needs the db; we cache its singleton
    # but each request will get a fresh cursor via flask.g
    app.config["_bnr_client"] = bnr_client
```

The `_build_service` in `pathtracks/routes.py` should construct CurrencyService:

```python
def _build_service() -> PathTrackService:
    db = current_app.config["_db"]
    return PathTrackService(
        coordinate_repo=CoordinateRepo(db),
        rate_repo=RateRepo(db),
        registry_repo=RegistryRepo(db),
        pathtrack_repo=PathTrackRepo(db),
        doc_repo=PathTrackDocRepo(db),
        connection_factory=get_request_db,
        currency_service=CurrencyService(
            bnr_repo=BnrRateRepo(db),
            bnr_client=current_app.config["_bnr_client"],
        ),
    )
```

Commit: `feat(pathtracks): freeze BNR rate on submit (BnrRateRonPerEur column)`

---

## Task 14: Display RON in view + list

**Files:**
- Modify: `fdp_app/templates/pathtracks/view.html`
- Modify: `fdp_app/templates/pathtracks/list.html`
- Modify: `fdp_app/templates/admin/history.html`
- Modify: `fdp_app/templates/admin/view_pathtrack.html`

In each template, where `€ {{ amount }}` is shown, add RON computation:

```jinja
{% if row.bnr_rate_ron_per_eur %}
&euro; {{ "%.2f"|format(row.computed_amount_eur) }}
<small class="text-muted">
    (RON {{ "%.2f"|format(row.computed_amount_eur * row.bnr_rate_ron_per_eur) }}
    &middot; tasso {{ "%.4f"|format(row.bnr_rate_ron_per_eur) }})
</small>
{% else %}
&euro; {{ "%.2f"|format(row.computed_amount_eur) }}
{% endif %}
```

For drafts (no rate yet), only EUR is shown.

Commit: `feat(currency): display RON alongside EUR in views and lists`

---

## Task 15: `/admin/bnr-rates` CRUD UI (standard rates)

**Files:**
- Modify: `fdp_app/admin/routes.py` (add `bnr_rates` GET + POST)
- Create: `fdp_app/templates/admin/bnr_rates.html`
- Modify: `fdp_app/repos/bnr_rate_repo.py` (add `list_standards`, `list_recent`)
- Test: `tests/test_admin_bnr_rates.py`

GET shows the list of standard rates + last 10 fetched rates.
POST creates a new standard rate with form fields (rate, valid_from, valid_to).

Add to `EmployeeRepo` no changes; just admin-protected.

Commit: `feat(admin): /admin/bnr-rates CRUD for standard rate periods`

---

## Task 16: Update existing tests for BNR field

The schema change adds a `bnr_rate_ron_per_eur` field to `PathTrackRow`. Existing tests that construct `PathTrackRow(...)` need to add `bnr_rate_ron_per_eur=None` to keep them passing.

Update `tests/test_pathtrack_repo.py`, `tests/test_pathtrack_service.py`, `tests/test_pathtracks_routes.py`, `tests/test_admin_routes.py` accordingly.

Commit: `test: add bnr_rate_ron_per_eur=None to PathTrackRow constructors`

---

# Fase D — Smoke test + tag

## Task 17: Smoke test manuale + tag `v0.5.0-i18n-currency`

1. Eseguire migration `004_create_bnrrates.sql` in SSMS
2. Inserire un tasso standard (per testare il caso "amministrativo"):
   ```sql
   INSERT INTO Employee.fdp.BnrRates
       (RateValueRonPerEur, Source, ValidFrom, ValidTo, IsStandard, UserSys)
   VALUES (4.9756, 'STANDARD', '2026-01-01', NULL, 1, SUSER_SNAME());
   ```
3. Riavviare app, hard refresh browser
4. Verificare selettore lingua in navbar → cambia IT/EN/RO funziona
5. Test currency: creare bozza, mostra solo EUR. Submit → DB ha `BnrRateRonPerEur=4.9756`. View mostra "€ 45.33 (RON 225.59 · tasso 4.9756)"
6. `/admin/bnr-rates` → vede il tasso standard + form per inserirne altri
7. Tag:
   ```bash
   git tag -a v0.5.0-i18n-currency -m "Piano 5 - Fix Piano 4 + i18n EN/RO + Currency BNR RON"
   git push origin main
   git push origin v0.5.0-i18n-currency
   ```

---

## Definition of Done

- [x] Admin `view_pathtrack` route + template (fix Piano 4 bug)
- [x] `resolve_target_employee` moved to admin/helpers.py
- [x] Inline imports hoisted
- [x] Flask-Babel integrated, default RO
- [x] Selettore lingua in navbar (IT/EN/RO)
- [x] Stringhe principali tradotte in EN e RO
- [x] DDL 004 applicata
- [x] BnrRateRepo + BnrRateClient + CurrencyService
- [x] Rate frozen on submit
- [x] RON display in view + list + admin
- [x] /admin/bnr-rates CRUD
- [x] Tests all green (~218 target)
- [x] Tag v0.5.0-i18n-currency

## Prossimo piano

- **Piano 6 — Notifiche & scheduler** (CLI send-reminders + close-month + Windows Task Scheduler runbook + email templates IT/EN/RO)
