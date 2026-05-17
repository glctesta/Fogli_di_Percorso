# Fogli di Percorso — Piano 1: Fondamenta

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Costruire le fondamenta dell'applicazione: setup del progetto Flask, script DDL per il database, autenticazione con `tbuserkey`, dashboard base e gestione errori. Al termine un utente con `FunctionCode > 60` può loggarsi e vedere la propria home, mentre un utente con `FC ≤ 60` viene respinto.

**Architecture:** Flask 3.x con factory pattern (`create_app`), blueprint per `auth`, pattern Repository su `pyodbc` (riusa `db_connection.py`/`config_manager.py` esistenti). Sessione server-side via cookie firmati. Test unitari con `pytest` e `unittest.mock` per i repository (test di integrazione DB rinviati al Piano 2/3).

**Tech Stack:** Python 3.11+, Flask 3.x, Flask-WTF (CSRF), `pyodbc`, `pytest`, `pytest-cov`, `freezegun`.

**Riferimento spec:** `docs/superpowers/specs/2026-05-17-fogli-di-percorso-design.md`

---

## File Structure

**Creati in questo piano:**
- `requirements.txt` — dipendenze runtime
- `requirements-dev.txt` — dipendenze test
- `.gitignore`
- `config/settings.py` — configurazione applicativa (non segreti)
- `config/workplace.json` — coordinate sede (placeholder editabile in produzione)
- `fdp_app/__init__.py` — `create_app()` factory
- `fdp_app/extensions.py` — istanze CSRF, logging
- `fdp_app/db.py` — wrapper attorno a `db_connection.DatabaseConnection` per dependency injection
- `fdp_app/auth/__init__.py`
- `fdp_app/auth/service.py` — `authenticate(nome_user, pwd) -> UserContext | None`
- `fdp_app/auth/routes.py` — Blueprint `/login`, `/logout`
- `fdp_app/auth/decorators.py` — `@login_required`
- `fdp_app/auth/rate_limit.py` — in-memory rate limiter
- `fdp_app/repos/__init__.py`
- `fdp_app/repos/employee_repo.py` — query di autenticazione
- `fdp_app/dashboard/__init__.py`
- `fdp_app/dashboard/routes.py` — Blueprint `/dashboard`
- `fdp_app/templates/base.html` — layout
- `fdp_app/templates/auth/login.html`
- `fdp_app/templates/dashboard/index.html`
- `fdp_app/templates/errors/403.html`, `404.html`, `500.html`
- `fdp_app/static/css/app.css`
- `app.py` — entry point per `flask run` e Waitress
- `sql/001_init.sql` — script DDL (eseguito manualmente in SSMS)
- `tests/__init__.py`
- `tests/conftest.py` — fixture Flask test client
- `tests/test_auth_service.py`
- `tests/test_auth_routes.py`
- `tests/test_rate_limit.py`
- `tests/test_dashboard.py`

**Riusati senza modifiche:**
- `db_connection.py`
- `config_manager.py`
- `email_connector.py` (non usato in questo piano)

---

## Task 1: Setup struttura progetto e dipendenze

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `.gitignore`
- Create: directory vuote `fdp_app/`, `tests/`, `config/`, `sql/`, `logs/`, `state/`

- [ ] **Step 1: Creare `requirements.txt`**

```
Flask==3.0.3
Flask-WTF==1.2.1
pyodbc==5.1.0
requests==2.32.3
openpyxl==3.1.5
python-dateutil==2.9.0.post0
cryptography==42.0.8
waitress==3.0.0
tzdata==2024.1
```

- [ ] **Step 2: Creare `requirements-dev.txt`**

```
-r requirements.txt
pytest==8.3.2
pytest-cov==5.0.0
responses==0.25.3
freezegun==1.5.1
```

- [ ] **Step 3: Creare `.gitignore`**

```
# Python
__pycache__/
*.py[cod]
*.pyo
.venv/
venv/
.pytest_cache/
.coverage
htmlcov/

# Logs / state
logs/
state/

# Secret files (existing)
encryption_key.key
email_key.key
db_config.enc
email_credentials.enc

# IDE
.vscode/
.idea/

# Plans / specs ARE committed
!docs/
```

- [ ] **Step 4: Creare le directory vuote con file `.gitkeep`**

```bash
mkdir -p fdp_app/auth fdp_app/dashboard fdp_app/repos fdp_app/templates/auth fdp_app/templates/dashboard fdp_app/templates/errors fdp_app/static/css
mkdir -p tests config sql logs state
touch logs/.gitkeep state/.gitkeep
```

- [ ] **Step 5: Installare le dipendenze**

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
```
Expected: nessun errore, `pip list` mostra Flask 3.0.3.

- [ ] **Step 6: Commit**

```bash
git init
git add requirements.txt requirements-dev.txt .gitignore logs/.gitkeep state/.gitkeep
git commit -m "chore: project scaffolding and dependencies"
```

---

## Task 2: Configurazione applicativa

**Files:**
- Create: `config/settings.py`
- Create: `config/workplace.json`
- Create: `config/__init__.py` (vuoto)

- [ ] **Step 1: Creare `config/__init__.py`** (file vuoto)

```python
```

- [ ] **Step 2: Creare `config/workplace.json`**

```json
{
  "name": "Sede aziendale",
  "address": "Via Esempio 1, 00000 Citta (IT)",
  "lat": 45.4642,
  "lon": 9.1900
}
```

> NOTA: `lat`/`lon` da aggiornare in produzione con i valori reali della sede.

- [ ] **Step 3: Creare `config/settings.py`**

```python
"""Configurazione applicativa (non segreti)."""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    """Settings letti da env var (con default) o file di configurazione."""

    # Flask
    SECRET_KEY: str = os.environ.get("FDP_SECRET_KEY") or secrets.token_hex(32)
    WTF_CSRF_ENABLED: bool = True
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"
    SESSION_COOKIE_SECURE: bool = os.environ.get("FDP_COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME: int = 8 * 60 * 60  # 8 ore in secondi

    # Routing
    OSRM_BASE: str = os.environ.get(
        "FDP_OSRM_BASE", "https://router.project-osrm.org"
    )
    ORS_API_KEY: str | None = os.environ.get("FDP_ORS_API_KEY")
    ORS_BASE: str = "https://api.openrouteservice.org"

    # Geocoding inverso
    NOMINATIM_BASE: str = "https://nominatim.openstreetmap.org"
    NOMINATIM_USER_AGENT: str = "FogliDiPercorso/1.0 (intranet)"

    # App
    APP_URL: str = os.environ.get("FDP_APP_URL", "http://localhost:5000")
    EMPLOYER_ID: int = 2
    MIN_FUNCTION_CODE_FOR_LOGIN: int = 60  # esclusivo: serve > 60
    REGISTRY_TYPE_ID: int = 790

    # Workplace
    @classmethod
    def workplace(cls) -> dict:
        with open(BASE_DIR / "config" / "workplace.json", encoding="utf-8") as f:
            return json.load(f)

    # Rate limit login
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_WINDOW_SECONDS: int = 15 * 60

    # Upload PDF
    UPLOAD_MAX_BYTES: int = 5 * 1024 * 1024
    UPLOAD_MAX_FILES_PER_PATHTRACK: int = 20
```

- [ ] **Step 4: Verificare che `Settings.workplace()` legga il file**

Creare un file di test ad-hoc temporaneo: `python -c "from config.settings import Settings; print(Settings.workplace())"`
Expected: `{'name': 'Sede aziendale', 'address': '...', 'lat': 45.4642, 'lon': 9.19}`
Cancellare ogni file ad-hoc dopo la verifica.

- [ ] **Step 5: Commit**

```bash
git add config/
git commit -m "feat(config): application settings and workplace coordinates"
```

---

## Task 3: Script DDL — migrazione database

**Files:**
- Create: `sql/001_init.sql`
- Create: `sql/README.md`

- [ ] **Step 1: Creare `sql/001_init.sql`**

```sql
-- =====================================================================
-- Fogli di Percorso - Migrazione iniziale
-- Eseguire UNA SOLA VOLTA in SQL Server Management Studio
-- come utente con permessi DDL su Employee.fdp
-- =====================================================================

USE Employee;
GO

-- ---------------------------------------------------------------------
-- 1. ALTER TABLE: PathTrackCoordinates
-- ---------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE Name = N'RoadKmToWorkplace'
      AND Object_ID = Object_ID(N'fdp.PathTrackCoordinates')
)
BEGIN
    ALTER TABLE fdp.PathTrackCoordinates
        ADD RoadKmToWorkplace DECIMAL(9,3) NULL;
END
GO

-- ---------------------------------------------------------------------
-- 2. ALTER TABLE: PathTrackDocs
-- ---------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE Name = N'DateOut'
      AND Object_ID = Object_ID(N'fdp.PathTrackDocs')
)
BEGIN
    ALTER TABLE fdp.PathTrackDocs
        ADD DateOut DATETIME NULL;
END
GO

-- ---------------------------------------------------------------------
-- 3. ALTER TABLE: PathTracks - colonne di calcolo congelato e soft-delete
-- ---------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE Name = N'ReimbursementType'
      AND Object_ID = Object_ID(N'fdp.PathTracks')
)
BEGIN
    ALTER TABLE fdp.PathTracks
        ADD ReimbursementType  CHAR(10)     NULL,
            NumberOfTrips      INT          NULL,
            RoadKm             DECIMAL(9,3) NULL,
            RateIdUsed         INT          NULL,
            TaxiTotalEur       DECIMAL(9,2) NULL,
            ComputedAmountEur  DECIMAL(9,2) NULL,
            DateOut            DATETIME     NULL;
END
GO

-- NOTA: le colonne sono NULL per non rompere eventuali dati esistenti.
-- L'applicazione le valorizzerà sempre per i nuovi record.
-- L'integrità è garantita lato app (vedi sezione 7.2 della spec).

-- ---------------------------------------------------------------------
-- 4. CREATE TABLE: PathTrackReimbursementRates
-- ---------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.tables
    WHERE Name = N'PathTrackReimbursementRates'
      AND SCHEMA_NAME(schema_id) = N'fdp'
)
BEGIN
    CREATE TABLE fdp.PathTrackReimbursementRates (
        RateId              INT IDENTITY(1,1) PRIMARY KEY,
        AvgConsumptionKmL   DECIMAL(6,2) NOT NULL,
        AvgFuelPriceEurL    DECIMAL(6,3) NOT NULL,
        ValidFrom           DATE NOT NULL,
        ValidTo             DATE NULL,
        DateSys             DATETIME NOT NULL DEFAULT GETDATE(),
        UserSys             NVARCHAR(100) NOT NULL
    );

    CREATE UNIQUE INDEX UX_Rates_ValidFrom
        ON fdp.PathTrackReimbursementRates(ValidFrom);
END
GO

-- ---------------------------------------------------------------------
-- 5. INDICI di supporto
-- ---------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_PathTrackCoordinates_Emp_Out'
      AND object_id = OBJECT_ID(N'fdp.PathTrackCoordinates')
)
BEGIN
    CREATE INDEX IX_PathTrackCoordinates_Emp_Out
        ON fdp.PathTrackCoordinates (EmployeerHireHistoryId, DateOut);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_PathTracks_Emp_Date'
      AND object_id = OBJECT_ID(N'fdp.PathTracks')
)
BEGIN
    CREATE INDEX IX_PathTracks_Emp_Date
        ON fdp.PathTracks (EmployeeHireHistoryId, DatePathTrack)
        WHERE DateOut IS NULL;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_PathTracks_Behalf_Date'
      AND object_id = OBJECT_ID(N'fdp.PathTracks')
)
BEGIN
    CREATE INDEX IX_PathTracks_Behalf_Date
        ON fdp.PathTracks (InBehalfOfId, DatePathTrack)
        WHERE DateOut IS NULL AND InBehalfOfId IS NOT NULL;
END
GO

PRINT 'Migrazione 001_init.sql completata.';
```

- [ ] **Step 2: Creare `sql/README.md`**

```markdown
# Script SQL — Fogli di Percorso

Script DDL da eseguire manualmente in SQL Server Management Studio (SSMS)
con un utente che ha permessi `db_ddladmin` su `Employee` e in particolare
sullo schema `fdp`.

## Ordine di esecuzione

1. `001_init.sql` — ALTER tabelle esistenti + CREATE `PathTrackReimbursementRates` + INDICI

Gli script sono idempotenti: si possono rieseguire senza danni.

## Dopo l'esecuzione di 001

Inserire la prima riga di rate:

```sql
INSERT INTO Employee.fdp.PathTrackReimbursementRates
    (AvgConsumptionKmL, AvgFuelPriceEurL, ValidFrom, ValidTo, UserSys)
VALUES
    (15.00, 1.700, '2026-01-01', NULL, SUSER_SNAME());
```
```

- [ ] **Step 3: Commit**

```bash
git add sql/
git commit -m "feat(db): initial DDL migration script and seed instructions"
```

---

## Task 4: Wrapper DB e factory `create_app`

**Files:**
- Create: `fdp_app/__init__.py`
- Create: `fdp_app/extensions.py`
- Create: `fdp_app/db.py`
- Create: `app.py`
- Test: `tests/__init__.py`, `tests/conftest.py`, `tests/test_app_boot.py`

- [ ] **Step 1: Creare `fdp_app/extensions.py`**

```python
"""Istanze condivise di estensioni Flask."""
from __future__ import annotations

from flask_wtf import CSRFProtect

csrf = CSRFProtect()
```

- [ ] **Step 2: Creare `fdp_app/db.py`**

```python
"""Wrapper attorno a db_connection.DatabaseConnection per dependency injection."""
from __future__ import annotations

from typing import Optional

from config_manager import ConfigManager
from db_connection import DatabaseConnection


class Database:
    """Wrapper iniettabile: in produzione delega a DatabaseConnection esistente.

    In test viene sostituito con MagicMock.
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None) -> None:
        self._cm = config_manager or ConfigManager()
        self._conn = DatabaseConnection(self._cm)

    def connect(self):
        return self._conn.connect()

    def disconnect(self) -> None:
        self._conn.disconnect()

    def cursor(self):
        """Ritorna un cursore. Caller responsabile della chiusura."""
        return self.connect().cursor()
```

- [ ] **Step 3: Creare `fdp_app/__init__.py`**

```python
"""Application factory."""
from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from flask import Flask, render_template

from config.settings import Settings
from fdp_app.db import Database
from fdp_app.extensions import csrf


def create_app(*, settings: type[Settings] | None = None,
               db: Database | None = None) -> Flask:
    """Costruisce l'app Flask. Le dipendenze possono essere iniettate per test."""
    settings = settings or Settings
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(settings)
    app.config["_settings_cls"] = settings

    # DI del database
    app.config["_db"] = db or Database()

    csrf.init_app(app)

    _configure_logging(app)
    _register_error_handlers(app)
    _register_blueprints(app)

    return app


def _configure_logging(app: Flask) -> None:
    logs_dir = Path(__file__).resolve().parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    handler = TimedRotatingFileHandler(
        logs_dir / "app.log",
        when="midnight",
        backupCount=14,
        encoding="utf-8",
    )
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Unhandled exception", exc_info=e)
        return render_template("errors/500.html"), 500


def _register_blueprints(app: Flask) -> None:
    # Importazioni interne per evitare cicli
    from fdp_app.auth.routes import bp as auth_bp
    from fdp_app.dashboard.routes import bp as dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
```

- [ ] **Step 4: Creare `app.py` (entry point)**

```python
"""Entry point per `flask run` e Waitress."""
from fdp_app import create_app

app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
```

- [ ] **Step 5: Creare `tests/__init__.py`** (file vuoto)

```python
```

- [ ] **Step 6: Creare `tests/conftest.py`**

```python
"""Fixture condivise pytest."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from config.settings import Settings
from fdp_app import create_app
from fdp_app.db import Database


class TestSettings(Settings):
    TESTING = True
    SECRET_KEY = "test-secret-key-only-for-pytest"
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False


@pytest.fixture
def mock_db():
    db = MagicMock(spec=Database)
    return db


@pytest.fixture
def app(mock_db):
    app = create_app(settings=TestSettings, db=mock_db)
    yield app


@pytest.fixture
def client(app):
    return app.test_client()
```

- [ ] **Step 7: Creare `tests/test_app_boot.py`**

```python
def test_app_can_be_created(app):
    """L'app Flask si avvia senza errori e ha config TESTING attivo."""
    assert app is not None
    assert app.config["TESTING"] is True


def test_unknown_route_returns_404(client):
    response = client.get("/this-route-does-not-exist")
    assert response.status_code == 404
```

- [ ] **Step 8: Eseguire i test (falliranno perché mancano template errors)**

```bash
pytest tests/test_app_boot.py -v
```
Expected: `test_app_can_be_created` PASS, `test_unknown_route_returns_404` FAIL (mancano i template di errore — li facciamo nel Task 5).

- [ ] **Step 9: Commit**

```bash
git add fdp_app/__init__.py fdp_app/extensions.py fdp_app/db.py app.py tests/__init__.py tests/conftest.py tests/test_app_boot.py
git commit -m "feat(app): Flask factory, db wrapper and base tests"
```

---

## Task 5: Template di base ed error pages

**Files:**
- Create: `fdp_app/templates/base.html`
- Create: `fdp_app/templates/errors/403.html`
- Create: `fdp_app/templates/errors/404.html`
- Create: `fdp_app/templates/errors/500.html`
- Create: `fdp_app/static/css/app.css`

- [ ] **Step 1: Creare `fdp_app/templates/base.html`**

```html
<!doctype html>
<html lang="it">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}Fogli di Percorso{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/app.css') }}">
    {% block head_extra %}{% endblock %}
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary mb-3">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('dashboard.index') if session.get('user_id') else url_for('auth.login') }}">Fogli di Percorso</a>
            {% if session.get('user_id') %}
            <div class="d-flex">
                <span class="navbar-text text-light me-3">{{ session.get('full_name') }}</span>
                <a class="btn btn-outline-light btn-sm" href="{{ url_for('auth.logout') }}">Esci</a>
            </div>
            {% endif %}
        </div>
    </nav>
    <main class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% for category, msg in messages %}
                <div class="alert alert-{{ category }}">{{ msg }}</div>
            {% endfor %}
        {% endwith %}
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

- [ ] **Step 2: Creare `fdp_app/templates/errors/403.html`**

```html
{% extends "base.html" %}
{% block title %}Accesso negato{% endblock %}
{% block content %}
<div class="alert alert-warning">
    <h3>Accesso negato</h3>
    <p>Non hai i permessi per accedere a questa pagina.</p>
    <a class="btn btn-primary" href="{{ url_for('dashboard.index') }}">Torna alla home</a>
</div>
{% endblock %}
```

- [ ] **Step 3: Creare `fdp_app/templates/errors/404.html`**

```html
{% extends "base.html" %}
{% block title %}Pagina non trovata{% endblock %}
{% block content %}
<div class="alert alert-info">
    <h3>Pagina non trovata</h3>
    <p>L'indirizzo richiesto non esiste.</p>
    <a class="btn btn-primary" href="{{ url_for('dashboard.index') if session.get('user_id') else url_for('auth.login') }}">Torna alla home</a>
</div>
{% endblock %}
```

- [ ] **Step 4: Creare `fdp_app/templates/errors/500.html`**

```html
{% extends "base.html" %}
{% block title %}Errore interno{% endblock %}
{% block content %}
<div class="alert alert-danger">
    <h3>Errore interno del server</h3>
    <p>Si e' verificato un errore imprevisto. L'amministratore e' stato informato.</p>
</div>
{% endblock %}
```

- [ ] **Step 5: Creare `fdp_app/static/css/app.css`**

```css
body {
    background-color: #f7f8fa;
}
.map-container {
    height: 480px;
    border: 1px solid #ced4da;
    border-radius: 6px;
}
.amount-preview {
    font-size: 1.5rem;
    font-weight: 600;
    color: #0d6efd;
}
```

- [ ] **Step 6: Rieseguire i test di Task 4 (ora il 404 funziona)**

```bash
pytest tests/test_app_boot.py -v
```
Expected: 2 passed (sia `test_app_can_be_created` sia `test_unknown_route_returns_404`).

- [ ] **Step 7: Commit**

```bash
git add fdp_app/templates/ fdp_app/static/
git commit -m "feat(ui): base layout, error pages and stylesheet"
```

---

## Task 6: `EmployeeRepo` con la query di autenticazione

**Files:**
- Create: `fdp_app/repos/__init__.py` (vuoto)
- Create: `fdp_app/repos/employee_repo.py`
- Test: `tests/test_employee_repo.py`

- [ ] **Step 1: Creare `fdp_app/repos/__init__.py`** (file vuoto)

```python
```

- [ ] **Step 2: Scrivere `tests/test_employee_repo.py` (test che fallisce)**

```python
"""Test del repository EmployeeRepo (mock pyodbc cursor)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from fdp_app.repos.employee_repo import EmployeeRepo, EmployeeAuthRow


def _make_db_with_rows(rows):
    """Costruisce un mock Database che ritorna `rows` da fetchone/fetchall."""
    db = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = rows[0] if rows else None
    cursor.fetchall.return_value = rows
    db.cursor.return_value = cursor
    return db


def test_find_user_by_nomeuser_returns_row_when_found():
    row = ("plain_pwd", 1234, "Rossi", "Mario", 77, 65)
    db = _make_db_with_rows([row])
    repo = EmployeeRepo(db)

    result = repo.find_user_by_nomeuser("mrossi")

    assert isinstance(result, EmployeeAuthRow)
    assert result.password == "plain_pwd"
    assert result.employee_hire_history_id == 1234
    assert result.surname == "Rossi"
    assert result.name == "Mario"
    assert result.sub_cdc_id == 77
    assert result.function_code == 65


def test_find_user_by_nomeuser_returns_none_when_missing():
    db = _make_db_with_rows([])
    repo = EmployeeRepo(db)

    result = repo.find_user_by_nomeuser("ghost")

    assert result is None


def test_find_user_by_nomeuser_passes_username_as_parameter():
    db = _make_db_with_rows([])
    repo = EmployeeRepo(db)

    repo.find_user_by_nomeuser("xyz")

    cursor = db.cursor.return_value
    # Si verifica che execute sia stato chiamato con la query e un solo parametro = "xyz"
    args, _kwargs = cursor.execute.call_args
    sql_text, *params = args
    assert "k.NomeUser = ?" in sql_text
    assert params == ["xyz"]
```

- [ ] **Step 3: Eseguire il test (deve fallire perché il modulo non esiste)**

```bash
pytest tests/test_employee_repo.py -v
```
Expected: `ModuleNotFoundError: No module named 'fdp_app.repos.employee_repo'`.

- [ ] **Step 4: Creare `fdp_app/repos/employee_repo.py`**

```python
"""Repository per i dati anagrafici degli employee."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


_QUERY_FIND_BY_NOMEUSER = """
SELECT k.pass,
       h.EmployeeHireHistoryId,
       e.EmployeeSurname,
       e.EmployeeName,
       s.SubCdcId,
       f.FunctionCode
FROM Employee.dbo.Employees e
JOIN resetservices.dbo.tbuserkey k
     ON e.EmployeeId = k.idanga
JOIN Employee.dbo.EmployeeHireHistory h
     ON h.EmployeeId = e.EmployeeId
    AND h.EndWorkDate IS NULL
    AND h.EmployeerId = 2
JOIN Employee.dbo.EmployeeCdcStories s
     ON s.EmployeeHireHistoryId = h.EmployeeHireHistoryId
    AND s.DateOut IS NULL
JOIN Employee.dbo.Functions f
     ON f.FunctionId = s.FunctionId
WHERE k.NomeUser = ?
"""


@dataclass(frozen=True)
class EmployeeAuthRow:
    """Risultato della query di login."""
    password: str
    employee_hire_history_id: int
    surname: str
    name: str
    sub_cdc_id: int
    function_code: int


class EmployeeRepo:
    """Accesso ai dati anagrafici."""

    def __init__(self, db) -> None:
        self._db = db

    def find_user_by_nomeuser(self, nome_user: str) -> Optional[EmployeeAuthRow]:
        cursor = self._db.cursor()
        cursor.execute(_QUERY_FIND_BY_NOMEUSER, nome_user)
        row = cursor.fetchone()
        if row is None:
            return None
        return EmployeeAuthRow(
            password=row[0],
            employee_hire_history_id=row[1],
            surname=row[2],
            name=row[3],
            sub_cdc_id=row[4],
            function_code=row[5],
        )
```

- [ ] **Step 5: Eseguire il test (deve passare)**

```bash
pytest tests/test_employee_repo.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add fdp_app/repos/ tests/test_employee_repo.py
git commit -m "feat(repos): EmployeeRepo with authentication lookup"
```

---

## Task 7: `auth.service.authenticate` (logica pura di autenticazione)

**Files:**
- Create: `fdp_app/auth/__init__.py` (vuoto)
- Create: `fdp_app/auth/service.py`
- Test: `tests/test_auth_service.py`

- [ ] **Step 1: Creare `fdp_app/auth/__init__.py`** (file vuoto)

```python
```

- [ ] **Step 2: Scrivere `tests/test_auth_service.py`**

```python
"""Test del service di autenticazione."""
from __future__ import annotations

from unittest.mock import MagicMock

from fdp_app.auth.service import AuthService, UserContext
from fdp_app.repos.employee_repo import EmployeeAuthRow


def _row(function_code: int, password: str = "secret") -> EmployeeAuthRow:
    return EmployeeAuthRow(
        password=password,
        employee_hire_history_id=999,
        surname="Bianchi",
        name="Luigi",
        sub_cdc_id=42,
        function_code=function_code,
    )


def test_authenticate_returns_user_context_for_valid_user_with_fc_gt_60():
    repo = MagicMock()
    repo.find_user_by_nomeuser.return_value = _row(function_code=65)
    service = AuthService(repo, min_function_code=60)

    ctx = service.authenticate("lbianchi", "secret")

    assert isinstance(ctx, UserContext)
    assert ctx.employee_hire_history_id == 999
    assert ctx.full_name == "Bianchi Luigi"
    assert ctx.sub_cdc_id == 42
    assert ctx.function_code == 65


def test_authenticate_rejects_user_with_fc_equal_to_60():
    """Threshold esclusivo: FC == 60 NON e' ammesso."""
    repo = MagicMock()
    repo.find_user_by_nomeuser.return_value = _row(function_code=60)
    service = AuthService(repo, min_function_code=60)

    ctx = service.authenticate("user60", "secret")

    assert ctx is None


def test_authenticate_rejects_user_with_fc_below_60():
    repo = MagicMock()
    repo.find_user_by_nomeuser.return_value = _row(function_code=40)
    service = AuthService(repo, min_function_code=60)

    ctx = service.authenticate("user40", "secret")

    assert ctx is None


def test_authenticate_rejects_wrong_password():
    repo = MagicMock()
    repo.find_user_by_nomeuser.return_value = _row(function_code=65, password="real")
    service = AuthService(repo, min_function_code=60)

    ctx = service.authenticate("user", "wrong")

    assert ctx is None


def test_authenticate_returns_none_when_user_not_found():
    repo = MagicMock()
    repo.find_user_by_nomeuser.return_value = None
    service = AuthService(repo, min_function_code=60)

    ctx = service.authenticate("ghost", "any")

    assert ctx is None


def test_authenticate_does_not_call_repo_when_inputs_empty():
    repo = MagicMock()
    service = AuthService(repo, min_function_code=60)

    assert service.authenticate("", "secret") is None
    assert service.authenticate("user", "") is None
    repo.find_user_by_nomeuser.assert_not_called()
```

- [ ] **Step 3: Eseguire i test (devono fallire)**

```bash
pytest tests/test_auth_service.py -v
```
Expected: `ModuleNotFoundError: No module named 'fdp_app.auth.service'`.

- [ ] **Step 4: Creare `fdp_app/auth/service.py`**

```python
"""Logica di autenticazione applicativa."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fdp_app.repos.employee_repo import EmployeeRepo


@dataclass(frozen=True)
class UserContext:
    """Contenuto della session dopo login riuscito."""
    employee_hire_history_id: int
    full_name: str
    sub_cdc_id: int
    function_code: int


class AuthService:
    """Verifica credenziali e perimetro di accesso (FC > min_function_code)."""

    def __init__(self, repo: EmployeeRepo, min_function_code: int) -> None:
        self._repo = repo
        self._min_fc = min_function_code

    def authenticate(self, nome_user: str, password: str) -> Optional[UserContext]:
        if not nome_user or not password:
            return None

        row = self._repo.find_user_by_nomeuser(nome_user)
        if row is None:
            return None

        if row.password != password:
            return None

        if row.function_code <= self._min_fc:
            return None

        return UserContext(
            employee_hire_history_id=row.employee_hire_history_id,
            full_name=f"{row.surname} {row.name}",
            sub_cdc_id=row.sub_cdc_id,
            function_code=row.function_code,
        )
```

- [ ] **Step 5: Eseguire i test (devono passare)**

```bash
pytest tests/test_auth_service.py -v
```
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add fdp_app/auth/__init__.py fdp_app/auth/service.py tests/test_auth_service.py
git commit -m "feat(auth): AuthService with FC>60 gating and password match"
```

---

## Task 8: Rate limiter login (in-memory)

**Files:**
- Create: `fdp_app/auth/rate_limit.py`
- Test: `tests/test_rate_limit.py`

- [ ] **Step 1: Scrivere `tests/test_rate_limit.py`**

```python
"""Test del rate limiter in-memory."""
from __future__ import annotations

from freezegun import freeze_time

from fdp_app.auth.rate_limit import LoginRateLimiter


def test_allows_first_attempts_below_limit():
    rl = LoginRateLimiter(max_attempts=3, window_seconds=60)
    assert rl.is_blocked("alice") is False
    rl.register_failure("alice")
    assert rl.is_blocked("alice") is False
    rl.register_failure("alice")
    assert rl.is_blocked("alice") is False


def test_blocks_after_max_attempts():
    rl = LoginRateLimiter(max_attempts=3, window_seconds=60)
    rl.register_failure("alice")
    rl.register_failure("alice")
    rl.register_failure("alice")
    assert rl.is_blocked("alice") is True


def test_separates_users():
    rl = LoginRateLimiter(max_attempts=2, window_seconds=60)
    rl.register_failure("alice")
    rl.register_failure("alice")
    assert rl.is_blocked("alice") is True
    assert rl.is_blocked("bob") is False


def test_window_expires():
    with freeze_time("2026-05-17 10:00:00") as frozen:
        rl = LoginRateLimiter(max_attempts=2, window_seconds=60)
        rl.register_failure("alice")
        rl.register_failure("alice")
        assert rl.is_blocked("alice") is True

        frozen.tick(delta=61)  # 61 secondi dopo
        assert rl.is_blocked("alice") is False


def test_register_success_clears_failures():
    rl = LoginRateLimiter(max_attempts=2, window_seconds=60)
    rl.register_failure("alice")
    rl.register_success("alice")
    rl.register_failure("alice")
    assert rl.is_blocked("alice") is False
```

- [ ] **Step 2: Eseguire i test (devono fallire)**

```bash
pytest tests/test_rate_limit.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Creare `fdp_app/auth/rate_limit.py`**

```python
"""Rate limiter in-memory per i tentativi di login."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict


class LoginRateLimiter:
    """Limita i tentativi di login falliti per `username` in una finestra mobile.

    Thread-safe. NON e' condiviso fra processi: in deploy multi-worker,
    ogni worker ha la propria copia (limite morbido, accettabile per V1).
    """

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self._max = max_attempts
        self._window = window_seconds
        self._failures: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _prune(self, key: str, now: float) -> None:
        q = self._failures[key]
        while q and (now - q[0]) > self._window:
            q.popleft()

    def is_blocked(self, key: str) -> bool:
        with self._lock:
            self._prune(key, time.time())
            return len(self._failures[key]) >= self._max

    def register_failure(self, key: str) -> None:
        with self._lock:
            now = time.time()
            self._prune(key, now)
            self._failures[key].append(now)

    def register_success(self, key: str) -> None:
        with self._lock:
            self._failures[key].clear()
```

- [ ] **Step 4: Eseguire i test (devono passare)**

```bash
pytest tests/test_rate_limit.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add fdp_app/auth/rate_limit.py tests/test_rate_limit.py
git commit -m "feat(auth): in-memory login rate limiter"
```

---

## Task 9: Decoratore `login_required`

**Files:**
- Create: `fdp_app/auth/decorators.py`
- Test: `tests/test_auth_decorators.py`

- [ ] **Step 1: Scrivere `tests/test_auth_decorators.py`**

```python
"""Test del decoratore login_required."""
from __future__ import annotations

from flask import Flask

from fdp_app.auth.decorators import login_required


def _build_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"

    @app.route("/secret")
    @login_required
    def secret():
        return "ok"

    return app


def test_login_required_redirects_when_anonymous():
    app = _build_app()
    client = app.test_client()
    response = client.get("/secret", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_login_required_allows_when_session_has_user_id():
    app = _build_app()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = 123
    response = client.get("/secret")
    assert response.status_code == 200
    assert response.data == b"ok"
```

- [ ] **Step 2: Eseguire i test (devono fallire)**

```bash
pytest tests/test_auth_decorators.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Creare `fdp_app/auth/decorators.py`**

```python
"""Decoratori di autorizzazione."""
from __future__ import annotations

from functools import wraps
from typing import Callable

from flask import redirect, session, url_for


def login_required(view: Callable) -> Callable:
    """Reindirizza a /login se non c'e' utente in sessione."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapper
```

- [ ] **Step 4: Eseguire i test (devono passare)**

```bash
pytest tests/test_auth_decorators.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add fdp_app/auth/decorators.py tests/test_auth_decorators.py
git commit -m "feat(auth): login_required decorator"
```

---

## Task 10: Route `/login` e `/logout`

**Files:**
- Create: `fdp_app/auth/routes.py`
- Create: `fdp_app/templates/auth/login.html`
- Modify: `fdp_app/__init__.py` (registrare repo/service nel `g` di Flask) — già pronto
- Test: `tests/test_auth_routes.py`

- [ ] **Step 1: Scrivere `tests/test_auth_routes.py`**

```python
"""Test end-to-end delle route di autenticazione (con mock del repo)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fdp_app.repos.employee_repo import EmployeeAuthRow


@pytest.fixture
def mock_repo():
    with patch("fdp_app.auth.routes.EmployeeRepo") as repo_cls:
        instance = MagicMock()
        repo_cls.return_value = instance
        yield instance


def test_get_login_page_renders(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"<form" in response.data.lower()
    assert b"nomeuser" in response.data.lower()


def test_post_login_success_with_fc_gt_60(client, mock_repo):
    mock_repo.find_user_by_nomeuser.return_value = EmployeeAuthRow(
        password="pw", employee_hire_history_id=10,
        surname="Rossi", name="Mario", sub_cdc_id=5, function_code=70,
    )
    response = client.post(
        "/login",
        data={"nome_user": "mrossi", "password": "pw"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]
    with client.session_transaction() as sess:
        assert sess["user_id"] == 10
        assert sess["full_name"] == "Rossi Mario"
        assert sess["sub_cdc_id"] == 5
        assert sess["function_code"] == 70


def test_post_login_rejects_fc_below_60(client, mock_repo):
    mock_repo.find_user_by_nomeuser.return_value = EmployeeAuthRow(
        password="pw", employee_hire_history_id=10,
        surname="Rossi", name="Mario", sub_cdc_id=5, function_code=40,
    )
    response = client.post(
        "/login",
        data={"nome_user": "mrossi", "password": "pw"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"credenziali" in response.data.lower()
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_post_login_rejects_wrong_password(client, mock_repo):
    mock_repo.find_user_by_nomeuser.return_value = EmployeeAuthRow(
        password="real", employee_hire_history_id=10,
        surname="Rossi", name="Mario", sub_cdc_id=5, function_code=70,
    )
    response = client.post(
        "/login",
        data={"nome_user": "mrossi", "password": "WRONG"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"credenziali" in response.data.lower()


def test_post_login_rejects_unknown_user(client, mock_repo):
    mock_repo.find_user_by_nomeuser.return_value = None
    response = client.post(
        "/login",
        data={"nome_user": "ghost", "password": "x"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"credenziali" in response.data.lower()


def test_logout_clears_session_and_redirects(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 99
        sess["full_name"] = "Test User"
    response = client.get("/logout", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_rate_limit_blocks_after_5_failures(client, mock_repo):
    mock_repo.find_user_by_nomeuser.return_value = None  # always fail
    for _ in range(5):
        client.post("/login", data={"nome_user": "spammer", "password": "x"})

    response = client.post(
        "/login",
        data={"nome_user": "spammer", "password": "x"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"troppi tentativi" in response.data.lower()
```

- [ ] **Step 2: Eseguire i test (devono fallire)**

```bash
pytest tests/test_auth_routes.py -v
```
Expected: `ModuleNotFoundError: No module named 'fdp_app.auth.routes'`.

- [ ] **Step 3: Creare `fdp_app/templates/auth/login.html`**

```html
{% extends "base.html" %}
{% block title %}Accedi - Fogli di Percorso{% endblock %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-md-5">
        <div class="card shadow-sm">
            <div class="card-body">
                <h3 class="card-title mb-3">Accedi</h3>
                <form method="post" novalidate>
                    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                    <div class="mb-3">
                        <label class="form-label" for="nome_user">Nome utente</label>
                        <input class="form-control" type="text" name="nome_user" id="nome_user" required autofocus>
                    </div>
                    <div class="mb-3">
                        <label class="form-label" for="password">Password</label>
                        <input class="form-control" type="password" name="password" id="password" required>
                    </div>
                    <button type="submit" class="btn btn-primary w-100">Entra</button>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 4: Creare `fdp_app/auth/routes.py`**

```python
"""Route di autenticazione."""
from __future__ import annotations

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request,
    session, url_for,
)

from fdp_app.auth.rate_limit import LoginRateLimiter
from fdp_app.auth.service import AuthService
from fdp_app.repos.employee_repo import EmployeeRepo

bp = Blueprint("auth", __name__)

# Singleton rate limiter (per processo). Inizializzato lazy.
_rate_limiter: LoginRateLimiter | None = None


def _get_rate_limiter() -> LoginRateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        s = current_app.config["_settings_cls"]
        _rate_limiter = LoginRateLimiter(
            max_attempts=s.LOGIN_MAX_ATTEMPTS,
            window_seconds=s.LOGIN_WINDOW_SECONDS,
        )
    return _rate_limiter


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("auth/login.html")

    nome_user = (request.form.get("nome_user") or "").strip()
    password = request.form.get("password") or ""

    rl = _get_rate_limiter()
    if rl.is_blocked(nome_user):
        flash("Troppi tentativi falliti, riprovare piu' tardi.", "danger")
        return render_template("auth/login.html"), 200

    db = current_app.config["_db"]
    repo = EmployeeRepo(db)
    s = current_app.config["_settings_cls"]
    service = AuthService(repo, min_function_code=s.MIN_FUNCTION_CODE_FOR_LOGIN)

    ctx = service.authenticate(nome_user, password)
    if ctx is None:
        rl.register_failure(nome_user)
        flash("Credenziali non valide.", "danger")
        current_app.logger.info("Login failed for %s", nome_user)
        return render_template("auth/login.html"), 200

    rl.register_success(nome_user)
    session.clear()
    session["user_id"] = ctx.employee_hire_history_id
    session["full_name"] = ctx.full_name
    session["sub_cdc_id"] = ctx.sub_cdc_id
    session["function_code"] = ctx.function_code
    session.permanent = True
    current_app.logger.info("Login OK for user_id=%s", ctx.employee_hire_history_id)
    return redirect(url_for("dashboard.index"))


@bp.route("/logout")
def logout():
    user_id = session.get("user_id")
    session.clear()
    current_app.logger.info("Logout user_id=%s", user_id)
    return redirect(url_for("auth.login"))
```

- [ ] **Step 5: Eseguire i test**

```bash
pytest tests/test_auth_routes.py -v
```
Expected: 7 passed. Se il rate limiter usa singleton globale e il test ordering causa interferenza, isolare con `monkeypatch` di `_rate_limiter = None` in una fixture autouse — non dovrebbe servire perché `spammer` e `mrossi` sono key diverse.

- [ ] **Step 6: Commit**

```bash
git add fdp_app/auth/routes.py fdp_app/templates/auth/ tests/test_auth_routes.py
git commit -m "feat(auth): /login and /logout with rate limit"
```

---

## Task 11: Dashboard base

**Files:**
- Create: `fdp_app/dashboard/__init__.py` (vuoto)
- Create: `fdp_app/dashboard/routes.py`
- Create: `fdp_app/templates/dashboard/index.html`
- Test: `tests/test_dashboard.py`

- [ ] **Step 1: Creare `fdp_app/dashboard/__init__.py`** (file vuoto)

```python
```

- [ ] **Step 2: Scrivere `tests/test_dashboard.py`**

```python
"""Test dashboard."""


def test_dashboard_redirects_anonymous_to_login(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_dashboard_renders_for_logged_user(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = 7
        sess["function_code"] = 65

    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"Rossi Mario" in response.data
    assert b"Benvenuto" in response.data


def test_root_redirects_to_dashboard(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]
```

- [ ] **Step 3: Eseguire i test (devono fallire)**

```bash
pytest tests/test_dashboard.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Creare `fdp_app/dashboard/routes.py`**

```python
"""Dashboard utente."""
from __future__ import annotations

from flask import Blueprint, redirect, render_template, session, url_for

from fdp_app.auth.decorators import login_required

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def root():
    return redirect(url_for("dashboard.index"))


@bp.route("/dashboard")
@login_required
def index():
    return render_template(
        "dashboard/index.html",
        full_name=session.get("full_name"),
        sub_cdc_id=session.get("sub_cdc_id"),
        function_code=session.get("function_code"),
    )
```

- [ ] **Step 5: Creare `fdp_app/templates/dashboard/index.html`**

```html
{% extends "base.html" %}
{% block title %}Home - Fogli di Percorso{% endblock %}
{% block content %}
<h2>Benvenuto, {{ full_name }}</h2>
<p class="text-muted">SubCdc: {{ sub_cdc_id }} - Codice Funzione: {{ function_code }}</p>

<div class="row mt-4">
    <div class="col-md-4">
        <div class="card">
            <div class="card-body">
                <h5 class="card-title">Punto di partenza</h5>
                <p class="card-text">Definisci o aggiorna il tuo punto di partenza sulla mappa.</p>
                <a class="btn btn-outline-primary disabled" href="#">Disponibile nel Piano 2</a>
            </div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card">
            <div class="card-body">
                <h5 class="card-title">Dichiarazione mensile</h5>
                <p class="card-text">Inserisci viaggi, carica i PDF e calcola il rimborso.</p>
                <a class="btn btn-outline-primary disabled" href="#">Disponibile nel Piano 3</a>
            </div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card">
            <div class="card-body">
                <h5 class="card-title">Amministrazione</h5>
                <p class="card-text">Rappresenta colleghi e consulta lo storico.</p>
                <a class="btn btn-outline-primary disabled" href="#">Disponibile nel Piano 4</a>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 6: Eseguire i test (devono passare)**

```bash
pytest tests/test_dashboard.py -v
```
Expected: 3 passed.

- [ ] **Step 7: Eseguire l'intera suite**

```bash
pytest -v --cov=fdp_app --cov-report=term-missing
```
Expected: tutti i test passano, coverage ≥80% sui moduli `fdp_app/auth` e `fdp_app/repos`.

- [ ] **Step 8: Commit**

```bash
git add fdp_app/dashboard/ fdp_app/templates/dashboard/ tests/test_dashboard.py
git commit -m "feat(dashboard): authenticated home with placeholders for future phases"
```

---

## Task 12: Smoke test manuale end-to-end

**Files:** nessuno

- [ ] **Step 1: Eseguire `001_init.sql` su SSMS** (DB di staging)

Procedura: aprire SSMS, connettersi al DB di staging, aprire `sql/001_init.sql`, eseguire (`F5`). Verificare in output: `Migrazione 001_init.sql completata.`

- [ ] **Step 2: Inserire il rate iniziale**

Eseguire in SSMS:
```sql
INSERT INTO Employee.fdp.PathTrackReimbursementRates
    (AvgConsumptionKmL, AvgFuelPriceEurL, ValidFrom, ValidTo, UserSys)
VALUES (15.00, 1.700, '2026-01-01', NULL, SUSER_SNAME());
```

- [ ] **Step 3: Configurare le credenziali DB**

In una shell Python:
```python
from config_manager import ConfigManager
ConfigManager().save_config(
    driver="ODBC Driver 17 for SQL Server",
    server="<server>",
    database="Employee",
    username="<user>",
    password="<password>",
)
```

- [ ] **Step 4: Avviare l'app**

```bash
.venv\Scripts\activate
flask --app app run
```
Expected: `Running on http://127.0.0.1:5000`.

- [ ] **Step 5: Login con utente reale FC>60**

Aprire browser su `http://127.0.0.1:5000/login`, inserire `NomeUser` e password di un utente noto con `FunctionCode > 60`.
Expected: redirect a `/dashboard`, nome cognome in navbar, card placeholder visibili.

- [ ] **Step 6: Login con utente FC<=60**

Provare con un utente con `FunctionCode <= 60`.
Expected: rimane su `/login`, messaggio "Credenziali non valide.".

- [ ] **Step 7: Login con password errata**

Expected: rimane su `/login`, messaggio "Credenziali non valide.".

- [ ] **Step 8: Logout**

Cliccare "Esci".
Expected: redirect a `/login`, sessione cancellata.

- [ ] **Step 9: Tag della Fase 1**

```bash
git tag -a v0.1.0-fondamenta -m "Piano 1 completato: setup, DDL, auth, dashboard"
```

---

## Definition of Done — Piano 1

- [x] `requirements.txt` e `requirements-dev.txt` installati senza errori
- [x] Script `sql/001_init.sql` eseguito sul DB target
- [x] Riga iniziale in `PathTrackReimbursementRates` presente
- [x] `pytest -v` → tutti i test verdi, coverage ≥80% sui moduli toccati
- [x] Login con utente `FC > 60` funzionante via browser
- [x] Login negato per `FC ≤ 60` e password errate
- [x] Logout azzera la sessione
- [x] Tag git `v0.1.0-fondamenta` creato

## Prossimi piani

- **Piano 2 — Punto di partenza** (mappa Leaflet + OSRM + CRUD `PathTrackCoordinates`)
- **Piano 3 — Dichiarazione mensile** (form + calcolo + transazione + SP Registro)
- **Piano 4 — Admin** (representable / history / export XLSX)
- **Piano 5 — Notifiche & scheduler** (CLI + email + idempotenza)
