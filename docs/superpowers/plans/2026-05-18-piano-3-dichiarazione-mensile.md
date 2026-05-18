# Fogli di Percorso — Piano 3: Dichiarazione mensile

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettere a un dipendente autenticato di registrare ogni mese (entro il 5 del mese successivo) il numero di viaggi effettuati, caricare i PDF di foglio di percorso e ricevute, ottenere il calcolo automatico del rimborso (carburante o taxi) e visualizzare/modificare/cancellare la dichiarazione entro la finestra di scadenza.

**Architecture:** Trasformare i moduli foundation (repo per `PathTracks`/`PathTrackDocs`/`PathTrackReimbursementRates`, client SP `Registro`, calcolatore di rimborso, validatore di scadenza) in un service `PathTrackService` che orchestra tutto dentro una transazione SQL Server (autocommit OFF). Route `/pathtracks/*` espongono CRUD lato HTTP con upload PDF (BLOB), CSRF e validazioni server-side. Refactor `Database` per usare `flask.g` connessione per richiesta.

**Tech Stack:** Python 3.11+, Flask 3.x, pyodbc (transazioni esplicite), `python-dateutil` (calcolo mese precedente), `zoneinfo` (Europe/Rome), `freezegun` per testare deadlines.

**Riferimento spec:** `docs/superpowers/specs/2026-05-17-fogli-di-percorso-design.md` (sezioni 5.2, 5.3, 6.3, 7.1, 7.2, 7.3, 7.4, 7.6)

**Prerequisito:** Piano 2 completato e taggato `v0.2.0-coordinate`. 64 test verdi.

---

## Struttura del Piano

- **Fase A** (Task 1-4): Pre-fix dal final review del Piano 2.
- **Fase B** (Task 5-8): Foundation (rates, registry, calculator, deadline).
- **Fase C** (Task 9-11): Persistenza (pathtracks repo, docs repo, service transazionale).
- **Fase D** (Task 12-18): UI e routing (form, upload PDF, view, edit, delete, list, dashboard link).
- **Fase E** (Task 19): Smoke test manuale + tag `v0.3.0-pathtracks`.

---

## File Structure

**File creati:**
- `fdp_app/repos/rate_repo.py` — lookup `PathTrackReimbursementRates` per data
- `fdp_app/repos/registry_repo.py` — chiamata SP `Employee.dbo.Registro`
- `fdp_app/repos/pathtrack_repo.py` — CRUD `PathTracks` con transazione
- `fdp_app/repos/doc_repo.py` — CRUD BLOB `PathTrackDocs`
- `fdp_app/pathtracks/calculator.py` — funzioni pure di calcolo rimborso
- `fdp_app/pathtracks/deadline.py` — verifica finestra di scadenza (Europe/Rome)
- `fdp_app/pathtracks/service.py` — orchestrazione transazionale
- `fdp_app/pathtracks/routes.py` — Blueprint `/pathtracks/...`
- `fdp_app/templates/pathtracks/new.html` — form inserimento
- `fdp_app/templates/pathtracks/view.html` — visualizzazione singola dichiarazione
- `fdp_app/templates/pathtracks/list.html` — storico personale
- `fdp_app/static/js/pathtracks.js` — UI dinamica (toggle CARBURANTE/TAXI, ricevute multi-riga, anteprima importo)
- `tests/test_rate_repo.py`
- `tests/test_registry_repo.py`
- `tests/test_calculator.py`
- `tests/test_deadline.py`
- `tests/test_pathtrack_repo.py`
- `tests/test_doc_repo.py`
- `tests/test_pathtrack_service.py`
- `tests/test_pathtracks_routes.py`

**File modificati:**
- `fdp_app/db.py` — passa a `flask.g` per per-request connection (rimuove `threading.Lock`)
- `fdp_app/__init__.py` — istanzia `RoutingClient` e `workplace` dict a startup, salvati in `app.config["_routing"]` e `app.config["_workplace"]`; registra blueprint `pathtracks`; teardown `flask.g.db` al shutdown della request
- `fdp_app/coordinates/routes.py` — usa `app.config["_routing"]` invece di costruirlo per request
- `fdp_app/repos/employee_repo.py` — usa nuovo Database API (`get_db()` per ottenere connection)
- `fdp_app/repos/coordinate_repo.py` — usa nuovo Database API
- `fdp_app/templates/dashboard/index.html` — card "Dichiarazione mensile" diventa attiva (link a `/pathtracks/new`)
- `tests/conftest.py` — pulizia: già a posto post-Piano 2
- `tests/test_secret_key_warning.py` — riscrivi `test_no_warning_in_testing_mode` per non essere vacuous
- `tests/test_coordinates_routes.py` — rinomina `test_post_delete_not_owned_returns_404` → `test_post_delete_not_owned_shows_warning`

---

# Fase A — Pre-fixes Piano 2

## Task 1: Riscrivere il test vacuous di SECRET_KEY warning

**Files:**
- Modify: `tests/test_secret_key_warning.py`

- [ ] **Step 1: Sostituire `test_no_warning_in_testing_mode` con la versione che cattura l'app build dentro caplog**

Aprire `tests/test_secret_key_warning.py`, trovare l'ultimo test:

```python
def test_no_warning_in_testing_mode(caplog, app):
    """In TESTING mode il warning e' silenziato (la fixture app usa TestSettings)."""
    # `app` fixture gia' costruisce l'app con TestSettings(TESTING=True)
    # ...
    assert "FDP_SECRET_KEY" not in caplog.text
```

Sostituirlo con:

```python
def test_no_warning_in_testing_mode_when_secret_key_missing(monkeypatch, caplog):
    """In TESTING mode il warning NON viene emesso anche se FDP_SECRET_KEY manca."""
    monkeypatch.delenv("FDP_SECRET_KEY", raising=False)

    from config.settings import Settings

    class TestSettingsLocal(Settings):
        TESTING = True
        SECRET_KEY = "test-secret"

    with caplog.at_level("WARNING"):
        create_app(settings=TestSettingsLocal, db=MagicMock(spec=Database))

    assert "FDP_SECRET_KEY" not in caplog.text
```

(Aggiungere `from config.settings import Settings` in cima al file se non presente, ma usare il `Settings` importato localmente dentro la funzione per evitare conflitti.)

- [ ] **Step 2: Eseguire i test**

```bash
.venv\Scripts\python.exe -m pytest tests/test_secret_key_warning.py -v
```
Expected: 3 passed (i 2 originali + il riscritto).

- [ ] **Step 3: Eseguire la suite completa**

```bash
.venv\Scripts\python.exe -m pytest -q
```
Expected: 64 passed.

- [ ] **Step 4: Commit**

```bash
git add tests/test_secret_key_warning.py
git commit -m "test: rewrite SECRET_KEY testing-mode warning test to be meaningful"
```

---

## Task 2: Rinominare il test misleading sui coordinate delete

**Files:**
- Modify: `tests/test_coordinates_routes.py`

- [ ] **Step 1: Rinominare il test**

Aprire `tests/test_coordinates_routes.py`, trovare `def test_post_delete_not_owned_returns_404`. Cambiare il nome in `def test_post_delete_not_owned_shows_warning`. Il corpo resta invariato.

- [ ] **Step 2: Eseguire i test**

```bash
.venv\Scripts\python.exe -m pytest tests/test_coordinates_routes.py -v
```
Expected: 9 passed (con il nuovo nome).

- [ ] **Step 3: Commit**

```bash
git add tests/test_coordinates_routes.py
git commit -m "test: rename misleading test name in coordinates_routes"
```

---

## Task 3: `Database` con `flask.g` per per-request connection

**Files:**
- Modify: `fdp_app/db.py`
- Modify: `fdp_app/__init__.py`
- Modify: `tests/test_db_lock.py` (rimuovere — il lock va via)
- Create: `tests/test_db_request_scope.py`

**Goal:** ogni richiesta HTTP ha la propria `pyodbc.Connection` cached in `flask.g`. La connessione viene chiusa al teardown della request. Il `Database` classe ora ha un metodo `get_request_connection()` che ritorna la connection scoped alla request corrente.

- [ ] **Step 1: Scrivere `tests/test_db_request_scope.py`**

```python
"""Verifica che Database fornisca connessioni per-request via flask.g."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, g

from fdp_app.db import Database, get_request_db


def _build_app_with_db(db):
    app = Flask(__name__)
    app.config["_db"] = db

    @app.route("/probe")
    def probe():
        conn1 = get_request_db()
        conn2 = get_request_db()
        # Stessa request -> stessa connection
        assert conn1 is conn2
        # Espone l'id per asserzione cross-request
        return {"conn_id": id(conn1)}

    return app


def test_same_request_reuses_one_connection():
    db = MagicMock(spec=Database)
    db.connect.side_effect = [MagicMock(name="conn1"), MagicMock(name="conn2")]
    app = _build_app_with_db(db)
    client = app.test_client()

    response = client.get("/probe")
    assert response.status_code == 200
    # Una sola request: connect() chiamato una sola volta
    assert db.connect.call_count == 1


def test_different_requests_get_different_connections():
    db = MagicMock(spec=Database)
    db.connect.side_effect = [
        MagicMock(name="conn1"),
        MagicMock(name="conn2"),
    ]
    app = _build_app_with_db(db)
    client = app.test_client()

    r1 = client.get("/probe")
    r2 = client.get("/probe")
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Due request -> due connect()
    assert db.connect.call_count == 2


def test_teardown_closes_request_connection():
    db = MagicMock(spec=Database)
    real_conn = MagicMock(name="real_conn")
    db.connect.return_value = real_conn
    app = _build_app_with_db(db)
    client = app.test_client()

    client.get("/probe")
    # Al teardown della request, il close va chiamato sulla connection
    real_conn.close.assert_called_once()
```

- [ ] **Step 2: Eseguire il test, deve fallire** (`get_request_db` non esiste)

```bash
.venv\Scripts\python.exe -m pytest tests/test_db_request_scope.py -v
```
Expected: ImportError / ModuleNotFoundError on `get_request_db`.

- [ ] **Step 3: Sostituire `fdp_app/db.py` con la nuova versione**

```python
"""Database con per-request connection via flask.g."""
from __future__ import annotations

from typing import Optional

from flask import current_app, g, has_app_context

from config_manager import ConfigManager
from db_connection import DatabaseConnection


class Database:
    """Wrapper iniettabile: usa DatabaseConnection legacy per costruire
    nuove connessioni `pyodbc`. Il lifecycle e' gestito da flask.g
    (vedi `get_request_db` e `teardown_request_db` in fdp_app/__init__.py).
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None) -> None:
        self._cm = config_manager or ConfigManager()

    def connect(self):
        """Crea una NUOVA pyodbc.Connection. Non e' cached qui; la cache
        e' su flask.g."""
        # Istanzia un DatabaseConnection fresco per ottenere una nuova connection
        # (DatabaseConnection.connect() cacherebbe internamente; usiamo nuove istanze
        # per garantire pulizia per-request).
        dc = DatabaseConnection(self._cm)
        return dc.connect()


def get_request_db():
    """Ritorna la connection associata alla request corrente.

    Crea e cacha su flask.g al primo accesso. La connection sara' chiusa
    da `teardown_request_db` al termine della request.
    """
    if not has_app_context():
        raise RuntimeError("get_request_db chiamato fuori da una request")
    if "db_conn" not in g:
        db: Database = current_app.config["_db"]
        g.db_conn = db.connect()
    return g.db_conn


def teardown_request_db(exception):
    """Da registrare con app.teardown_appcontext. Chiude la connection."""
    conn = g.pop("db_conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
```

- [ ] **Step 4: Registrare il teardown in `fdp_app/__init__.py`**

Dopo `_register_blueprints(app)`, aggiungere:

```python
    from fdp_app.db import teardown_request_db
    app.teardown_appcontext(teardown_request_db)
```

- [ ] **Step 5: Aggiornare i repository per usare `get_request_db()`**

I repository attualmente fanno `cursor = self._db.cursor()`. Adesso devono usare `get_request_db()` per ottenere la connection e chiamare `connection.cursor()`.

In `fdp_app/repos/employee_repo.py`, modificare:

```python
class EmployeeRepo:
    def __init__(self, db) -> None:
        self._db = db
```
in:
```python
class EmployeeRepo:
    """Accepts either a Database for legacy callers or relies on flask.g.

    In production: callers pass `current_app.config["_db"]` and the repo
    uses get_request_db() internally for per-request scoping.
    In test: callers can still pass a MagicMock; the legacy `db.cursor()`
    path is preserved.
    """

    def __init__(self, db) -> None:
        self._db = db
```

E il metodo `find_user_by_nomeuser`:

DA:
```python
    def find_user_by_nomeuser(self, nome_user: str) -> Optional[EmployeeAuthRow]:
        cursor = self._db.cursor()
```
A:
```python
    def find_user_by_nomeuser(self, nome_user: str) -> Optional[EmployeeAuthRow]:
        cursor = self._open_cursor()
```

E aggiungere il metodo `_open_cursor`:

```python
    def _open_cursor(self):
        """Apre un cursore. In production usa flask.g; in test delega a self._db.cursor()."""
        from flask import has_app_context
        if has_app_context():
            from fdp_app.db import get_request_db
            return get_request_db().cursor()
        return self._db.cursor()
```

Stessa modifica in `fdp_app/repos/coordinate_repo.py`: ogni `cursor = self._db.cursor()` diventa `cursor = self._open_cursor()`, e aggiungi il metodo `_open_cursor` con la stessa logica.

- [ ] **Step 6: Rimuovere `tests/test_db_lock.py` (la Lock non c'e' piu')**

```bash
git rm tests/test_db_lock.py
```

- [ ] **Step 7: Eseguire i test, devono passare**

```bash
.venv\Scripts\python.exe -m pytest tests/test_db_request_scope.py -v
.venv\Scripts\python.exe -m pytest -q
```
Expected: 3 passed in test_db_request_scope.py + 65 passed total (era 64 con test_db_lock; -2 lock + 3 new = +1 net = 65).

- [ ] **Step 8: Commit**

```bash
git add fdp_app/db.py fdp_app/__init__.py fdp_app/repos/employee_repo.py fdp_app/repos/coordinate_repo.py tests/test_db_request_scope.py tests/test_db_lock.py
git commit -m "refactor(db): per-request connection via flask.g, remove threading lock"
```

---

## Task 4: `RoutingClient` e `workplace` app-scoped (cache funzionante)

**Files:**
- Modify: `fdp_app/__init__.py`
- Modify: `fdp_app/coordinates/routes.py`
- Test: `tests/test_routing_app_scope.py` (nuovo)

- [ ] **Step 1: Scrivere `tests/test_routing_app_scope.py`**

```python
"""Verifica che RoutingClient sia istanziato una sola volta a startup."""
from __future__ import annotations

from unittest.mock import MagicMock

from config.settings import Settings
from fdp_app import create_app
from fdp_app.db import Database
from fdp_app.pathtracks.routing import RoutingClient


def test_routing_client_stored_in_app_config():
    class S(Settings):
        TESTING = True
        SECRET_KEY = "test"
        WTF_CSRF_ENABLED = False

    app = create_app(settings=S, db=MagicMock(spec=Database))
    assert isinstance(app.config["_routing"], RoutingClient)


def test_workplace_dict_stored_in_app_config():
    class S(Settings):
        TESTING = True
        SECRET_KEY = "test"
        WTF_CSRF_ENABLED = False

    app = create_app(settings=S, db=MagicMock(spec=Database))
    wp = app.config["_workplace"]
    assert "lat" in wp
    assert "lon" in wp
    assert "name" in wp


def test_routing_client_is_singleton_per_app():
    class S(Settings):
        TESTING = True
        SECRET_KEY = "test"
        WTF_CSRF_ENABLED = False

    app = create_app(settings=S, db=MagicMock(spec=Database))
    r1 = app.config["_routing"]
    r2 = app.config["_routing"]
    assert r1 is r2
```

- [ ] **Step 2: Eseguire i test, devono fallire**

```bash
.venv\Scripts\python.exe -m pytest tests/test_routing_app_scope.py -v
```
Expected: KeyError perche' `_routing` e `_workplace` non sono in app.config.

- [ ] **Step 3: Modificare `fdp_app/__init__.py`**

Dentro `create_app`, dopo `app.config["_db"] = db or Database()`, aggiungere:

```python
    from fdp_app.pathtracks.routing import RoutingClient
    app.config["_routing"] = RoutingClient(
        osrm_base=settings.OSRM_BASE,
        ors_base=settings.ORS_BASE,
        ors_api_key=settings.ORS_API_KEY,
    )
    app.config["_workplace"] = settings.workplace()
```

- [ ] **Step 4: Aggiornare `fdp_app/coordinates/routes.py` `_build_service`**

Sostituire:

```python
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
```

con:

```python
def _build_service() -> CoordinateService:
    db = current_app.config["_db"]
    repo = CoordinateRepo(db)
    routing = current_app.config["_routing"]
    workplace = current_app.config["_workplace"]
    return CoordinateService(repo=repo, routing=routing, workplace=workplace)
```

E nella `index()`, sostituire la seconda chiamata a `workplace()`:

DA:
```python
    workplace = current_app.config["_settings_cls"].workplace()
```
A:
```python
    workplace = current_app.config["_workplace"]
```

- [ ] **Step 5: Eseguire tutti i test**

```bash
.venv\Scripts\python.exe -m pytest -q
```
Expected: 68 passed (65 + 3 new).

- [ ] **Step 6: Commit**

```bash
git add fdp_app/__init__.py fdp_app/coordinates/routes.py tests/test_routing_app_scope.py
git commit -m "refactor(app): RoutingClient and workplace cached in app.config at startup"
```

---

# Fase B — Foundation

## Task 5: `RateRepo` — lookup rate per data

**Files:**
- Create: `fdp_app/repos/rate_repo.py`
- Test: `tests/test_rate_repo.py`

- [ ] **Step 1: Scrivere `tests/test_rate_repo.py`**

```python
"""Test del repository RateRepo."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from fdp_app.repos.rate_repo import RateRepo, Rate


def _make_db(fetchone=None):
    db = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    db.cursor.return_value = cursor
    return db, cursor


def test_find_for_date_returns_none_when_no_match():
    db, cursor = _make_db(fetchone=None)
    repo = RateRepo(db)

    result = repo.find_for_date(date(2026, 4, 1))

    assert result is None
    cursor.close.assert_called_once()


def test_find_for_date_returns_rate_when_found():
    db, cursor = _make_db(fetchone=(7, 15.00, 1.700))
    repo = RateRepo(db)

    result = repo.find_for_date(date(2026, 4, 1))

    assert isinstance(result, Rate)
    assert result.rate_id == 7
    assert result.avg_consumption_km_l == pytest.approx(15.00)
    assert result.avg_fuel_price_eur_l == pytest.approx(1.700)


def test_find_for_date_query_uses_validity_window():
    db, cursor = _make_db(fetchone=None)
    repo = RateRepo(db)

    repo.find_for_date(date(2026, 4, 1))

    sql_text, *params = cursor.execute.call_args[0]
    assert "ValidFrom <= ?" in sql_text
    assert "ValidTo IS NULL OR ValidTo >= ?" in sql_text
    assert params == [date(2026, 4, 1), date(2026, 4, 1)]
```

- [ ] **Step 2: Run, must fail**

```bash
.venv\Scripts\python.exe -m pytest tests/test_rate_repo.py -v
```

- [ ] **Step 3: Creare `fdp_app/repos/rate_repo.py`**

```python
"""Repository per fdp.PathTrackReimbursementRates."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from flask import has_app_context


_QUERY = """
SELECT TOP 1 RateId, AvgConsumptionKmL, AvgFuelPriceEurL
FROM Employee.fdp.PathTrackReimbursementRates
WHERE ValidFrom <= ?
  AND (ValidTo IS NULL OR ValidTo >= ?)
ORDER BY ValidFrom DESC
"""


@dataclass(frozen=True)
class Rate:
    rate_id: int
    avg_consumption_km_l: float
    avg_fuel_price_eur_l: float


class RateRepo:
    def __init__(self, db) -> None:
        self._db = db

    def _open_cursor(self):
        if has_app_context():
            from fdp_app.db import get_request_db
            return get_request_db().cursor()
        return self._db.cursor()

    def find_for_date(self, target_date: date) -> Optional[Rate]:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY, target_date, target_date)
            row = cursor.fetchone()
        finally:
            cursor.close()
        if row is None:
            return None
        return Rate(
            rate_id=int(row[0]),
            avg_consumption_km_l=float(row[1]),
            avg_fuel_price_eur_l=float(row[2]),
        )
```

- [ ] **Step 4: Run, must pass**

```bash
.venv\Scripts\python.exe -m pytest tests/test_rate_repo.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Full suite**

```bash
.venv\Scripts\python.exe -m pytest -q
```
Expected: 71 passed (68 + 3).

- [ ] **Step 6: Commit**

```bash
git add fdp_app/repos/rate_repo.py tests/test_rate_repo.py
git commit -m "feat(repos): RateRepo for PathTrackReimbursementRates lookup"
```

---

## Task 6: `RegistryRepo` — chiamata SP `Employee.dbo.Registro`

**Files:**
- Create: `fdp_app/repos/registry_repo.py`
- Test: `tests/test_registry_repo.py`

- [ ] **Step 1: Scrivere `tests/test_registry_repo.py`**

```python
"""Test del repository RegistryRepo (chiamata SP)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from fdp_app.repos.registry_repo import RegistryRepo


def _make_db(fetchone=None):
    db = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    db.cursor.return_value = cursor
    return db, cursor


def test_generate_new_registry_id_returns_int():
    db, cursor = _make_db(fetchone=(12345,))
    repo = RegistryRepo(db)

    result = repo.generate(issued_by_full_name="Rossi Mario")

    assert result == 12345
    cursor.close.assert_called_once()


def test_generate_calls_sp_with_correct_parameters():
    db, cursor = _make_db(fetchone=(1,))
    repo = RegistryRepo(db)

    repo.generate(issued_by_full_name="Bianchi Luigi")

    sql_text, *params = cursor.execute.call_args[0]
    assert "Employee.dbo.Registro" in sql_text
    assert "@RegistryTypeId" in sql_text
    assert "@anno" in sql_text
    assert "@DataDocumento" in sql_text
    assert "@IussedBy" in sql_text
    assert "@EmployeerId" in sql_text
    # Params: 790, anno, data, "Bianchi Luigi", 2
    assert params[0] == 790
    assert params[-1] == 2
    assert "Bianchi Luigi" in params


def test_generate_raises_if_sp_returns_no_row():
    db, cursor = _make_db(fetchone=None)
    repo = RegistryRepo(db)

    with pytest.raises(RuntimeError, match="non ha restituito"):
        repo.generate(issued_by_full_name="x")


def test_generate_closes_cursor_on_exception():
    db, cursor = _make_db()
    cursor.execute.side_effect = RuntimeError("DB down")
    repo = RegistryRepo(db)

    with pytest.raises(RuntimeError):
        repo.generate(issued_by_full_name="x")
    cursor.close.assert_called_once()
```

- [ ] **Step 2: Run, must fail**

```bash
.venv\Scripts\python.exe -m pytest tests/test_registry_repo.py -v
```

- [ ] **Step 3: Creare `fdp_app/repos/registry_repo.py`**

```python
"""Repository per la chiamata a Employee.dbo.Registro SP.

La SP assegna un nuovo RegistryId per `RegistryTypeId=790` (Fogli di Percorso).
Parametri:
    @RegistryTypeId = 790
    @anno = YEAR(GETDATE())
    @DataDocumento = GETDATE()
    @IussedBy = <cognome nome dell'utente loggato>
    @EmployeerId = 2

La SP restituisce il nuovo RegistryId come risultato (SELECT finale).
"""
from __future__ import annotations

from flask import has_app_context


# Chiamiamo la SP con EXEC. Usiamo un SELECT esplicito che attende il risultato
# come prima riga del rowset, perche' la SP fa SELECT @new_id alla fine.
_SP_CALL = """
EXEC Employee.dbo.Registro
    @RegistryTypeId = ?,
    @anno = YEAR(GETDATE()),
    @DataDocumento = GETDATE(),
    @IussedBy = ?,
    @EmployeerId = ?
"""


class RegistryRepo:
    REGISTRY_TYPE_ID = 790
    EMPLOYER_ID = 2

    def __init__(self, db) -> None:
        self._db = db

    def _open_cursor(self):
        if has_app_context():
            from fdp_app.db import get_request_db
            return get_request_db().cursor()
        return self._db.cursor()

    def generate(self, *, issued_by_full_name: str) -> int:
        cursor = self._open_cursor()
        try:
            cursor.execute(
                _SP_CALL,
                self.REGISTRY_TYPE_ID,
                issued_by_full_name,
                self.EMPLOYER_ID,
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError(
                    "Employee.dbo.Registro non ha restituito alcun RegistryId"
                )
            return int(row[0])
        finally:
            cursor.close()
```

- [ ] **Step 4: Run, must pass**

```bash
.venv\Scripts\python.exe -m pytest tests/test_registry_repo.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Full suite**

```bash
.venv\Scripts\python.exe -m pytest -q
```
Expected: 75 passed (71 + 4).

- [ ] **Step 6: Commit**

```bash
git add fdp_app/repos/registry_repo.py tests/test_registry_repo.py
git commit -m "feat(repos): RegistryRepo to invoke Employee.dbo.Registro SP"
```

---

## Task 7: `ReimbursementCalculator` — funzioni pure di calcolo

**Files:**
- Create: `fdp_app/pathtracks/calculator.py`
- Test: `tests/test_calculator.py`

- [ ] **Step 1: Scrivere `tests/test_calculator.py`**

```python
"""Test del calcolatore di rimborso."""
from __future__ import annotations

from decimal import Decimal

import pytest

from fdp_app.pathtracks.calculator import (
    compute_fuel_reimbursement,
    compute_taxi_reimbursement,
)


def test_fuel_basic_case():
    # 10 km one-way * 2 (A/R) * 20 viaggi / 15 km-l * 1.700 eur/l
    # = 10 * 2 * 20 / 15 * 1.7 = 45.333...
    amount = compute_fuel_reimbursement(
        road_km_one_way=10.0,
        number_of_trips=20,
        avg_consumption_km_l=15.0,
        avg_fuel_price_eur_l=1.700,
    )
    assert amount == pytest.approx(45.33, abs=0.01)


def test_fuel_zero_trips_returns_zero():
    amount = compute_fuel_reimbursement(
        road_km_one_way=10.0,
        number_of_trips=0,
        avg_consumption_km_l=15.0,
        avg_fuel_price_eur_l=1.700,
    )
    assert amount == 0.0


def test_fuel_rounded_to_two_decimals():
    # Verifica che il risultato sia troncato/arrotondato a 2 decimali
    amount = compute_fuel_reimbursement(
        road_km_one_way=7.777,
        number_of_trips=3,
        avg_consumption_km_l=12.5,
        avg_fuel_price_eur_l=1.852,
    )
    # 7.777 * 2 * 3 / 12.5 * 1.852 = 6.9136...
    # round half-even a 2 decimali = 6.91
    assert amount == pytest.approx(6.91, abs=0.01)


def test_fuel_raises_on_zero_consumption():
    with pytest.raises(ValueError, match="consumo"):
        compute_fuel_reimbursement(
            road_km_one_way=10.0,
            number_of_trips=20,
            avg_consumption_km_l=0.0,
            avg_fuel_price_eur_l=1.7,
        )


def test_fuel_raises_on_negative_inputs():
    with pytest.raises(ValueError):
        compute_fuel_reimbursement(
            road_km_one_way=-1.0,
            number_of_trips=10,
            avg_consumption_km_l=15.0,
            avg_fuel_price_eur_l=1.7,
        )


def test_taxi_sums_amounts():
    amount = compute_taxi_reimbursement([12.50, 8.30, 15.00])
    assert amount == pytest.approx(35.80, abs=0.01)


def test_taxi_empty_list_returns_zero():
    amount = compute_taxi_reimbursement([])
    assert amount == 0.0


def test_taxi_raises_on_negative_amount():
    with pytest.raises(ValueError, match="negat"):
        compute_taxi_reimbursement([10.0, -5.0])


def test_taxi_rounded_to_two_decimals():
    amount = compute_taxi_reimbursement([3.333, 2.222, 1.111])
    # 6.666 -> round half-even -> 6.67 o 6.66? round() banker -> 6.67 (3+2+1=6.666 -> 6.67)
    # Verifica precisa: 6.666 round() = 6.67 (con ROUND_HALF_UP)
    assert amount == pytest.approx(6.67, abs=0.01)
```

- [ ] **Step 2: Run, must fail**

- [ ] **Step 3: Creare `fdp_app/pathtracks/calculator.py`**

```python
"""Funzioni pure per il calcolo dei rimborsi.

Le funzioni accettano float per semplicita' e ritornano float arrotondati
a 2 decimali (centesimi di euro). Per esigenze contabili future si potra'
sostituire `float` con `Decimal`.

Formule (vedi spec sezione 7.1):
- Carburante: ComputedAmount = round((RoadKm * 2 * NumberOfTrips / AvgConsumptionKmL) * AvgFuelPriceEurL, 2)
- Taxi: ComputedAmount = sum(receipt_amounts), arrotondato a 2 decimali
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable


def _round_to_eur(value: float) -> float:
    """Arrotonda a 2 decimali con ROUND_HALF_UP (banking standard EU)."""
    d = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(d)


def compute_fuel_reimbursement(
    *,
    road_km_one_way: float,
    number_of_trips: int,
    avg_consumption_km_l: float,
    avg_fuel_price_eur_l: float,
) -> float:
    """Calcola il rimborso carburante in euro.

    Raises ValueError se gli input sono negativi o se consumption e' 0.
    """
    if road_km_one_way < 0:
        raise ValueError("road_km_one_way non puo' essere negativo")
    if number_of_trips < 0:
        raise ValueError("number_of_trips non puo' essere negativo")
    if avg_consumption_km_l <= 0:
        raise ValueError(
            f"avg_consumption_km_l (consumo) deve essere > 0, ricevuto {avg_consumption_km_l}"
        )
    if avg_fuel_price_eur_l < 0:
        raise ValueError("avg_fuel_price_eur_l non puo' essere negativo")

    if number_of_trips == 0:
        return 0.0

    liters_needed = (road_km_one_way * 2 * number_of_trips) / avg_consumption_km_l
    eur = liters_needed * avg_fuel_price_eur_l
    return _round_to_eur(eur)


def compute_taxi_reimbursement(receipt_amounts: Iterable[float]) -> float:
    """Somma degli importi delle ricevute taxi, arrotondato a 2 decimali.

    Raises ValueError se un importo e' negativo.
    """
    total = 0.0
    for amount in receipt_amounts:
        if amount < 0:
            raise ValueError(f"importo ricevuta negativo non ammesso: {amount}")
        total += amount
    return _round_to_eur(total)
```

- [ ] **Step 4: Run, must pass**

```bash
.venv\Scripts\python.exe -m pytest tests/test_calculator.py -v
```
Expected: 9 passed.

- [ ] **Step 5: Full suite**

Expected: 84 passed (75 + 9).

- [ ] **Step 6: Commit**

```bash
git add fdp_app/pathtracks/calculator.py tests/test_calculator.py
git commit -m "feat(pathtracks): pure reimbursement calculator (fuel + taxi)"
```

---

## Task 8: `DeadlineService` — finestra di scadenza Europe/Rome

**Files:**
- Create: `fdp_app/pathtracks/deadline.py`
- Test: `tests/test_deadline.py`

- [ ] **Step 1: Scrivere `tests/test_deadline.py`**

```python
"""Test della finestra di scadenza (entro il 5 del mese successivo)."""
from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from fdp_app.pathtracks.deadline import (
    is_open_for_month,
    previous_month_first_day,
)


def test_previous_month_jan_to_dec():
    with freeze_time("2026-01-15 10:00:00"):
        assert previous_month_first_day() == date(2025, 12, 1)


def test_previous_month_mid_year():
    with freeze_time("2026-05-15 10:00:00"):
        assert previous_month_first_day() == date(2026, 4, 1)


def test_window_open_first_day_of_next_month():
    # Mese di riferimento aprile 2026: finestra dal 1 al 5 maggio 2026
    with freeze_time("2026-05-01 00:00:00+02:00"):  # Europe/Rome (CEST)
        assert is_open_for_month(date(2026, 4, 1)) is True


def test_window_open_fifth_day_late():
    with freeze_time("2026-05-05 23:59:59+02:00"):
        assert is_open_for_month(date(2026, 4, 1)) is True


def test_window_closed_sixth_day():
    with freeze_time("2026-05-06 00:00:00+02:00"):
        assert is_open_for_month(date(2026, 4, 1)) is False


def test_window_closed_before_period():
    # Mese di riferimento aprile, oggi 15 aprile = ancora dentro il mese, troppo presto
    with freeze_time("2026-04-15 10:00:00+02:00"):
        assert is_open_for_month(date(2026, 4, 1)) is False


def test_window_closed_for_older_month():
    # Mese di riferimento marzo 2026: finestra era 1-5 aprile 2026
    with freeze_time("2026-05-15 10:00:00+02:00"):
        assert is_open_for_month(date(2026, 3, 1)) is False


def test_window_open_for_december_in_january():
    with freeze_time("2026-01-05 23:59:59+01:00"):  # CET
        assert is_open_for_month(date(2025, 12, 1)) is True
```

- [ ] **Step 2: Run, must fail**

- [ ] **Step 3: Creare `fdp_app/pathtracks/deadline.py`**

```python
"""Logica di finestra di scadenza (entro il 5 del mese successivo, Europe/Rome)."""
from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta

_TZ = ZoneInfo("Europe/Rome")


def previous_month_first_day(today: date | None = None) -> date:
    """Primo giorno del mese precedente alla data corrente (Europe/Rome)."""
    if today is None:
        today = datetime.now(_TZ).date()
    return (today.replace(day=1) - relativedelta(days=1)).replace(day=1)


def is_open_for_month(date_path_track: date) -> bool:
    """True se siamo nella finestra di apertura per il mese `date_path_track`.

    Finestra: dal giorno 1 alle 00:00:00 al giorno 5 alle 23:59:59 del
    mese successivo a `date_path_track`, in fuso Europe/Rome.
    """
    now = datetime.now(_TZ)
    # Primo giorno del mese SUCCESSIVO a date_path_track
    next_month_first = (date_path_track + relativedelta(months=1)).replace(day=1)
    window_open = datetime.combine(next_month_first, time(0, 0, 0), tzinfo=_TZ)
    window_close = datetime.combine(
        next_month_first.replace(day=5), time(23, 59, 59), tzinfo=_TZ
    )
    return window_open <= now <= window_close
```

- [ ] **Step 4: Run, must pass**

Expected: 8 passed.

- [ ] **Step 5: Full suite**

Expected: 92 passed (84 + 8).

- [ ] **Step 6: Commit**

```bash
git add fdp_app/pathtracks/deadline.py tests/test_deadline.py
git commit -m "feat(pathtracks): deadline window check in Europe/Rome timezone"
```

---

# Fase C — Persistenza

## Task 9: `PathTrackRepo` — CRUD con transazione

**Files:**
- Create: `fdp_app/repos/pathtrack_repo.py`
- Test: `tests/test_pathtrack_repo.py`

- [ ] **Step 1: Scrivere `tests/test_pathtrack_repo.py`**

```python
"""Test del repository PathTrackRepo."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from fdp_app.repos.pathtrack_repo import (
    PathTrackRepo,
    PathTrackRow,
)


def _make_db(fetchone=None, fetchall=None):
    db = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    cursor.fetchall.return_value = fetchall or []
    db.cursor.return_value = cursor
    return db, cursor


def test_find_active_for_month_returns_none_when_no_row():
    db, _ = _make_db(fetchone=None)
    repo = PathTrackRepo(db)

    result = repo.find_active_for_month(
        employee_hire_history_id=10, date_path_track=date(2026, 4, 1)
    )
    assert result is None


def test_find_active_for_month_returns_row():
    db, cursor = _make_db(fetchone=(
        100,        # PathTrackId
        500,        # RegistryId
        date(2026, 4, 1),  # DatePathTrack
        99,         # DeclaratedPathId (FK coordinate)
        None,       # InBehalfOfId
        "CARBURANTE",
        15,         # NumberOfTrips
        10.5,       # RoadKm
        3,          # RateIdUsed
        None,       # TaxiTotalEur
        53.55,      # ComputedAmountEur
    ))
    repo = PathTrackRepo(db)

    result = repo.find_active_for_month(
        employee_hire_history_id=10, date_path_track=date(2026, 4, 1)
    )

    assert isinstance(result, PathTrackRow)
    assert result.path_track_id == 100
    assert result.registry_id == 500
    assert result.reimbursement_type == "CARBURANTE"
    assert result.computed_amount_eur == pytest.approx(53.55)


def test_insert_returns_new_id():
    db, cursor = _make_db(fetchone=(200,))
    repo = PathTrackRepo(db)

    new_id = repo.insert(
        employee_hire_history_id=10,
        registry_id=500,
        date_path_track=date(2026, 4, 1),
        declarated_path_id=99,
        in_behalf_of_id=None,
        reimbursement_type="CARBURANTE",
        number_of_trips=15,
        road_km=10.5,
        rate_id_used=3,
        taxi_total_eur=None,
        computed_amount_eur=53.55,
    )

    assert new_id == 200
    sql_text, *params = cursor.execute.call_args[0]
    assert "INSERT INTO Employee.fdp.PathTracks" in sql_text
    # Verifica che params siano nel giusto ordine
    assert 10 in params  # employee_hire_history_id
    assert 500 in params  # registry_id
    assert "CARBURANTE" in params


def test_soft_delete_returns_true_when_row_deleted():
    db, cursor = _make_db()
    cursor.rowcount = 1
    repo = PathTrackRepo(db)

    deleted = repo.soft_delete(path_track_id=100, employee_hire_history_id=10)

    assert deleted is True
    sql_text, *params = cursor.execute.call_args[0]
    assert "SET DateOut = GETDATE()" in sql_text
    assert "EmployeeHireHistoryId = ?" in sql_text
    assert params == [100, 10]


def test_soft_delete_returns_false_when_no_rows_affected():
    db, cursor = _make_db()
    cursor.rowcount = 0
    repo = PathTrackRepo(db)

    deleted = repo.soft_delete(path_track_id=999, employee_hire_history_id=10)
    assert deleted is False


def test_list_for_employee_returns_rows():
    db, cursor = _make_db(fetchall=[
        (1, 100, date(2026, 4, 1), 99, None, "CARBURANTE", 15, 10.5, 3, None, 53.55),
        (2, 101, date(2026, 3, 1), 99, None, "TAXI", 10, 8.0, None, 45.0, 45.0),
    ])
    repo = PathTrackRepo(db)

    rows = repo.list_for_employee(employee_hire_history_id=10)

    assert len(rows) == 2
    assert rows[0].path_track_id == 1
    assert rows[1].reimbursement_type == "TAXI"
```

- [ ] **Step 2: Run, must fail**

- [ ] **Step 3: Creare `fdp_app/repos/pathtrack_repo.py`**

```python
"""Repository per fdp.PathTracks (dichiarazione mensile)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from flask import has_app_context


_QUERY_FIND_FOR_MONTH = """
SELECT TOP 1
    PathTrackId, RegistryId, DatePathTrack, DeclaratedPathId, InBehalfOfId,
    ReimbursementType, NumberOfTrips, RoadKm, RateIdUsed, TaxiTotalEur,
    ComputedAmountEur
FROM Employee.fdp.PathTracks
WHERE EmployeeHireHistoryId = ?
  AND DatePathTrack = ?
  AND DateOut IS NULL
"""

_QUERY_FIND_BY_ID = """
SELECT TOP 1
    PathTrackId, RegistryId, DatePathTrack, DeclaratedPathId, InBehalfOfId,
    ReimbursementType, NumberOfTrips, RoadKm, RateIdUsed, TaxiTotalEur,
    ComputedAmountEur
FROM Employee.fdp.PathTracks
WHERE PathTrackId = ?
  AND EmployeeHireHistoryId = ?
  AND DateOut IS NULL
"""

_QUERY_INSERT = """
INSERT INTO Employee.fdp.PathTracks
    (EmployeeHireHistoryId, RegistryId, DatePathTrack, DeclaratedPathId,
     InBehalfOfId, ReimbursementType, NumberOfTrips, RoadKm, RateIdUsed,
     TaxiTotalEur, ComputedAmountEur, DateOut, ReceivedOn, DateSys)
OUTPUT INSERTED.PathTrackId
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, GETDATE())
"""

_QUERY_SOFT_DELETE = """
UPDATE Employee.fdp.PathTracks
SET DateOut = GETDATE()
WHERE PathTrackId = ?
  AND EmployeeHireHistoryId = ?
  AND DateOut IS NULL
"""

_QUERY_LIST = """
SELECT
    PathTrackId, RegistryId, DatePathTrack, DeclaratedPathId, InBehalfOfId,
    ReimbursementType, NumberOfTrips, RoadKm, RateIdUsed, TaxiTotalEur,
    ComputedAmountEur
FROM Employee.fdp.PathTracks
WHERE EmployeeHireHistoryId = ?
  AND DateOut IS NULL
ORDER BY DatePathTrack DESC
"""


@dataclass(frozen=True)
class PathTrackRow:
    path_track_id: int
    registry_id: int
    date_path_track: date
    declarated_path_id: int
    in_behalf_of_id: Optional[int]
    reimbursement_type: str
    number_of_trips: int
    road_km: float
    rate_id_used: Optional[int]
    taxi_total_eur: Optional[float]
    computed_amount_eur: float


def _row_to_obj(row) -> PathTrackRow:
    return PathTrackRow(
        path_track_id=row[0],
        registry_id=row[1],
        date_path_track=row[2],
        declarated_path_id=row[3],
        in_behalf_of_id=row[4],
        reimbursement_type=row[5].rstrip() if isinstance(row[5], str) else row[5],  # CHAR(10) padding
        number_of_trips=row[6],
        road_km=float(row[7]),
        rate_id_used=row[8],
        taxi_total_eur=float(row[9]) if row[9] is not None else None,
        computed_amount_eur=float(row[10]),
    )


class PathTrackRepo:
    def __init__(self, db) -> None:
        self._db = db

    def _open_cursor(self):
        if has_app_context():
            from fdp_app.db import get_request_db
            return get_request_db().cursor()
        return self._db.cursor()

    def find_active_for_month(
        self, *, employee_hire_history_id: int, date_path_track: date
    ) -> Optional[PathTrackRow]:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_FIND_FOR_MONTH, employee_hire_history_id, date_path_track)
            row = cursor.fetchone()
        finally:
            cursor.close()
        return _row_to_obj(row) if row else None

    def find_by_id(
        self, *, path_track_id: int, employee_hire_history_id: int
    ) -> Optional[PathTrackRow]:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_FIND_BY_ID, path_track_id, employee_hire_history_id)
            row = cursor.fetchone()
        finally:
            cursor.close()
        return _row_to_obj(row) if row else None

    def insert(
        self,
        *,
        employee_hire_history_id: int,
        registry_id: int,
        date_path_track: date,
        declarated_path_id: int,
        in_behalf_of_id: Optional[int],
        reimbursement_type: str,
        number_of_trips: int,
        road_km: float,
        rate_id_used: Optional[int],
        taxi_total_eur: Optional[float],
        computed_amount_eur: float,
    ) -> int:
        cursor = self._open_cursor()
        try:
            cursor.execute(
                _QUERY_INSERT,
                employee_hire_history_id,
                registry_id,
                date_path_track,
                declarated_path_id,
                in_behalf_of_id,
                reimbursement_type,
                number_of_trips,
                road_km,
                rate_id_used,
                taxi_total_eur,
                computed_amount_eur,
            )
            row = cursor.fetchone()
            return int(row[0])
        finally:
            cursor.close()

    def soft_delete(
        self, *, path_track_id: int, employee_hire_history_id: int
    ) -> bool:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_SOFT_DELETE, path_track_id, employee_hire_history_id)
            return cursor.rowcount > 0
        finally:
            cursor.close()

    def list_for_employee(
        self, *, employee_hire_history_id: int
    ) -> List[PathTrackRow]:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_LIST, employee_hire_history_id)
            rows = cursor.fetchall()
        finally:
            cursor.close()
        return [_row_to_obj(r) for r in rows]
```

- [ ] **Step 4: Run, must pass**

Expected: 6 passed.

- [ ] **Step 5: Full suite**

Expected: 98 passed (92 + 6).

- [ ] **Step 6: Commit**

```bash
git add fdp_app/repos/pathtrack_repo.py tests/test_pathtrack_repo.py
git commit -m "feat(repos): PathTrackRepo with CRUD and list operations"
```

---

## Task 10: `PathTrackDocRepo` — BLOB su PathTrackDocs

**Files:**
- Create: `fdp_app/repos/doc_repo.py`
- Test: `tests/test_doc_repo.py`

- [ ] **Step 1: Scrivere `tests/test_doc_repo.py`**

```python
"""Test del repository PathTrackDocRepo."""
from __future__ import annotations

from unittest.mock import MagicMock

from fdp_app.repos.doc_repo import PathTrackDocRepo, PathTrackDocRow


def _make_db(fetchone=None, fetchall=None):
    db = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    cursor.fetchall.return_value = fetchall or []
    db.cursor.return_value = cursor
    return db, cursor


def test_insert_returns_new_doc_id():
    db, cursor = _make_db(fetchone=(42,))
    repo = PathTrackDocRepo(db)

    doc_id = repo.insert(
        path_track_id=100,
        doc_title="Foglio di Percorso - Aprile 2026",
        pdf_bytes=b"%PDF-1.4\n...some content...",
    )

    assert doc_id == 42
    sql_text, *params = cursor.execute.call_args[0]
    assert "INSERT INTO Employee.fdp.PathTrackDocs" in sql_text
    assert "DocumentOfTrackPath" in sql_text
    # Params: blob, title, path_track_id
    assert b"%PDF-" in params[0]
    assert "Foglio di Percorso - Aprile 2026" in params


def test_list_for_pathtrack_returns_rows():
    db, cursor = _make_db(fetchall=[
        (1, "Foglio percorso", 100),
        (2, "Ricevuta 1", 100),
    ])
    repo = PathTrackDocRepo(db)

    rows = repo.list_for_pathtrack(path_track_id=100)

    assert len(rows) == 2
    assert rows[0].doc_id == 1
    assert rows[0].doc_title == "Foglio percorso"
    assert rows[1].doc_title == "Ricevuta 1"


def test_soft_delete_for_pathtrack_marks_all_docs():
    db, cursor = _make_db()
    cursor.rowcount = 3
    repo = PathTrackDocRepo(db)

    count = repo.soft_delete_all_for_pathtrack(path_track_id=100)

    assert count == 3
    sql_text, *params = cursor.execute.call_args[0]
    assert "UPDATE Employee.fdp.PathTrackDocs" in sql_text
    assert "SET DateOut = GETDATE()" in sql_text
    assert "PathTrackId = ?" in sql_text
    assert params == [100]


def test_get_blob_returns_pdf_bytes():
    db, cursor = _make_db(fetchone=(b"%PDF-1.4\n...", "Title"))
    repo = PathTrackDocRepo(db)

    pdf_bytes, title = repo.get_blob(doc_id=42)

    assert pdf_bytes.startswith(b"%PDF-")
    assert title == "Title"
```

- [ ] **Step 2: Run, must fail**

- [ ] **Step 3: Creare `fdp_app/repos/doc_repo.py`**

```python
"""Repository per fdp.PathTrackDocs (BLOB dei PDF caricati)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from flask import has_app_context


_QUERY_INSERT = """
INSERT INTO Employee.fdp.PathTrackDocs
    (DocumentOfTrackPath, DocTitle, PathTrackId, DateSys)
OUTPUT INSERTED.PathTrackDocId
VALUES (?, ?, ?, GETDATE())
"""

_QUERY_LIST = """
SELECT PathTrackDocId, DocTitle, PathTrackId
FROM Employee.fdp.PathTrackDocs
WHERE PathTrackId = ?
  AND DateOut IS NULL
ORDER BY PathTrackDocId
"""

_QUERY_SOFT_DELETE_ALL = """
UPDATE Employee.fdp.PathTrackDocs
SET DateOut = GETDATE()
WHERE PathTrackId = ?
  AND DateOut IS NULL
"""

_QUERY_GET_BLOB = """
SELECT TOP 1 DocumentOfTrackPath, DocTitle
FROM Employee.fdp.PathTrackDocs
WHERE PathTrackDocId = ?
  AND DateOut IS NULL
"""


@dataclass(frozen=True)
class PathTrackDocRow:
    doc_id: int
    doc_title: str
    path_track_id: int


class PathTrackDocRepo:
    def __init__(self, db) -> None:
        self._db = db

    def _open_cursor(self):
        if has_app_context():
            from fdp_app.db import get_request_db
            return get_request_db().cursor()
        return self._db.cursor()

    def insert(self, *, path_track_id: int, doc_title: str, pdf_bytes: bytes) -> int:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_INSERT, pdf_bytes, doc_title, path_track_id)
            row = cursor.fetchone()
            return int(row[0])
        finally:
            cursor.close()

    def list_for_pathtrack(self, *, path_track_id: int) -> List[PathTrackDocRow]:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_LIST, path_track_id)
            rows = cursor.fetchall()
        finally:
            cursor.close()
        return [PathTrackDocRow(doc_id=r[0], doc_title=r[1], path_track_id=r[2]) for r in rows]

    def soft_delete_all_for_pathtrack(self, *, path_track_id: int) -> int:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_SOFT_DELETE_ALL, path_track_id)
            return int(cursor.rowcount)
        finally:
            cursor.close()

    def get_blob(self, *, doc_id: int) -> Tuple[bytes, str]:
        cursor = self._open_cursor()
        try:
            cursor.execute(_QUERY_GET_BLOB, doc_id)
            row = cursor.fetchone()
            if row is None:
                raise FileNotFoundError(f"Documento {doc_id} non trovato")
            return bytes(row[0]), str(row[1])
        finally:
            cursor.close()
```

- [ ] **Step 4: Run, must pass**

Expected: 4 passed.

- [ ] **Step 5: Full suite**

Expected: 102 passed (98 + 4).

- [ ] **Step 6: Commit**

```bash
git add fdp_app/repos/doc_repo.py tests/test_doc_repo.py
git commit -m "feat(repos): PathTrackDocRepo for PDF BLOB storage"
```

---

## Task 11: `PathTrackService` — transazione orchestrata

**Files:**
- Create: `fdp_app/pathtracks/service.py`
- Test: `tests/test_pathtrack_service.py`

**Goal:** orchestra `RateRepo` + `RegistryRepo` + `PathTrackRepo` + `PathTrackDocRepo` + `CoordinateRepo` + `ReimbursementCalculator`. Crea una dichiarazione mensile in transazione (BEGIN TRAN / COMMIT / ROLLBACK manuale su pyodbc).

- [ ] **Step 1: Scrivere `tests/test_pathtrack_service.py`**

```python
"""Test del PathTrackService (orchestrazione transazionale)."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from fdp_app.pathtracks.service import (
    PathTrackService,
    DeadlineClosedError,
    NoActiveCoordinateError,
    NoRateConfiguredError,
    DuplicateDeclarationError,
    InvalidInputError,
)
from fdp_app.repos.coordinate_repo import ActiveCoordinate
from fdp_app.repos.pathtrack_repo import PathTrackRow
from fdp_app.repos.rate_repo import Rate


def _make_service():
    repos = {
        "coordinate": MagicMock(),
        "rate": MagicMock(),
        "registry": MagicMock(),
        "pathtrack": MagicMock(),
        "doc": MagicMock(),
    }
    connection = MagicMock()
    svc = PathTrackService(
        coordinate_repo=repos["coordinate"],
        rate_repo=repos["rate"],
        registry_repo=repos["registry"],
        pathtrack_repo=repos["pathtrack"],
        doc_repo=repos["doc"],
        connection_factory=lambda: connection,
    )
    return svc, repos, connection


def test_create_fuel_happy_path():
    svc, repos, conn = _make_service()
    repos["coordinate"].find_active.return_value = ActiveCoordinate(
        coordinate_id=99, label="Casa", lat=45.0, lon=9.0, road_km_to_workplace=10.0,
    )
    repos["rate"].find_for_date.return_value = Rate(
        rate_id=3, avg_consumption_km_l=15.0, avg_fuel_price_eur_l=1.7,
    )
    repos["registry"].generate.return_value = 500
    repos["pathtrack"].find_active_for_month.return_value = None
    repos["pathtrack"].insert.return_value = 100
    repos["doc"].insert.return_value = 1

    new_id = svc.create_fuel(
        employee_hire_history_id=10,
        full_name="Rossi Mario",
        date_path_track=date(2026, 4, 1),
        number_of_trips=20,
        sheet_pdf=b"%PDF-foglio-percorso",
        receipt_pdfs=[b"%PDF-ricevuta-1"],
    )

    assert new_id == 100
    # Rate lookup chiamato col target date
    repos["rate"].find_for_date.assert_called_once_with(date(2026, 4, 1))
    # Registry chiamato con full name
    repos["registry"].generate.assert_called_once()
    # Insert con computed amount = 10 * 2 * 20 / 15 * 1.7 = 45.33
    insert_kwargs = repos["pathtrack"].insert.call_args.kwargs
    assert insert_kwargs["reimbursement_type"] == "CARBURANTE"
    assert insert_kwargs["computed_amount_eur"] == pytest.approx(45.33, abs=0.01)
    assert insert_kwargs["registry_id"] == 500
    # 2 documenti inseriti (1 sheet + 1 ricevuta)
    assert repos["doc"].insert.call_count == 2
    # Transazione: commit chiamato
    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()


def test_create_taxi_happy_path():
    svc, repos, conn = _make_service()
    repos["coordinate"].find_active.return_value = ActiveCoordinate(
        coordinate_id=99, label="Casa", lat=45.0, lon=9.0, road_km_to_workplace=10.0,
    )
    repos["pathtrack"].find_active_for_month.return_value = None
    repos["registry"].generate.return_value = 600
    repos["pathtrack"].insert.return_value = 101
    repos["doc"].insert.return_value = 5

    new_id = svc.create_taxi(
        employee_hire_history_id=10,
        full_name="Bianchi Luigi",
        date_path_track=date(2026, 4, 1),
        number_of_trips=10,
        receipt_amounts=[12.50, 8.30],
        sheet_pdf=b"%PDF-foglio",
        receipt_pdfs=[b"%PDF-r1", b"%PDF-r2"],
    )

    assert new_id == 101
    repos["rate"].find_for_date.assert_not_called()  # no rate per taxi
    insert_kwargs = repos["pathtrack"].insert.call_args.kwargs
    assert insert_kwargs["reimbursement_type"] == "TAXI"
    assert insert_kwargs["rate_id_used"] is None
    assert insert_kwargs["taxi_total_eur"] == pytest.approx(20.80)
    assert insert_kwargs["computed_amount_eur"] == pytest.approx(20.80)
    # 1 sheet + 2 ricevute = 3 doc
    assert repos["doc"].insert.call_count == 3
    conn.commit.assert_called_once()


def test_create_rolls_back_on_insert_failure():
    svc, repos, conn = _make_service()
    repos["coordinate"].find_active.return_value = ActiveCoordinate(
        coordinate_id=99, label="Casa", lat=45.0, lon=9.0, road_km_to_workplace=10.0,
    )
    repos["rate"].find_for_date.return_value = Rate(3, 15.0, 1.7)
    repos["registry"].generate.return_value = 500
    repos["pathtrack"].find_active_for_month.return_value = None
    repos["pathtrack"].insert.side_effect = RuntimeError("DB error")

    with pytest.raises(RuntimeError):
        svc.create_fuel(
            employee_hire_history_id=10,
            full_name="x",
            date_path_track=date(2026, 4, 1),
            number_of_trips=10,
            sheet_pdf=b"%PDF-",
            receipt_pdfs=[b"%PDF-"],
        )

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()


def test_create_raises_when_no_active_coordinate():
    svc, repos, _ = _make_service()
    repos["coordinate"].find_active.return_value = None

    with pytest.raises(NoActiveCoordinateError):
        svc.create_fuel(
            employee_hire_history_id=10,
            full_name="x",
            date_path_track=date(2026, 4, 1),
            number_of_trips=10,
            sheet_pdf=b"%PDF-",
            receipt_pdfs=[b"%PDF-"],
        )

    repos["pathtrack"].insert.assert_not_called()


def test_create_raises_when_no_rate_configured_for_fuel():
    svc, repos, _ = _make_service()
    repos["coordinate"].find_active.return_value = ActiveCoordinate(
        99, "x", 1, 2, 3,
    )
    repos["rate"].find_for_date.return_value = None

    with pytest.raises(NoRateConfiguredError):
        svc.create_fuel(
            employee_hire_history_id=10,
            full_name="x",
            date_path_track=date(2026, 4, 1),
            number_of_trips=10,
            sheet_pdf=b"%PDF-",
            receipt_pdfs=[b"%PDF-"],
        )


def test_create_raises_when_already_active_for_month():
    svc, repos, _ = _make_service()
    repos["coordinate"].find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 3)
    repos["rate"].find_for_date.return_value = Rate(3, 15.0, 1.7)
    repos["pathtrack"].find_active_for_month.return_value = PathTrackRow(
        path_track_id=999, registry_id=1, date_path_track=date(2026, 4, 1),
        declarated_path_id=99, in_behalf_of_id=None,
        reimbursement_type="CARBURANTE", number_of_trips=10, road_km=10.0,
        rate_id_used=3, taxi_total_eur=None, computed_amount_eur=10.0,
    )

    with pytest.raises(DuplicateDeclarationError):
        svc.create_fuel(
            employee_hire_history_id=10,
            full_name="x",
            date_path_track=date(2026, 4, 1),
            number_of_trips=10,
            sheet_pdf=b"%PDF-",
            receipt_pdfs=[b"%PDF-"],
        )


def test_create_fuel_validates_trips_range():
    svc, repos, _ = _make_service()
    repos["coordinate"].find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 3)

    with pytest.raises(InvalidInputError, match="viaggi"):
        svc.create_fuel(
            employee_hire_history_id=10,
            full_name="x",
            date_path_track=date(2026, 4, 1),
            number_of_trips=0,  # Invalid
            sheet_pdf=b"%PDF-",
            receipt_pdfs=[b"%PDF-"],
        )


def test_create_fuel_requires_at_least_one_sheet_pdf():
    svc, repos, _ = _make_service()
    repos["coordinate"].find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 3)

    with pytest.raises(InvalidInputError, match="foglio"):
        svc.create_fuel(
            employee_hire_history_id=10,
            full_name="x",
            date_path_track=date(2026, 4, 1),
            number_of_trips=10,
            sheet_pdf=None,
            receipt_pdfs=[b"%PDF-"],
        )


def test_create_taxi_requires_at_least_one_receipt():
    svc, repos, _ = _make_service()
    repos["coordinate"].find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 3)

    with pytest.raises(InvalidInputError, match="ricevuta"):
        svc.create_taxi(
            employee_hire_history_id=10,
            full_name="x",
            date_path_track=date(2026, 4, 1),
            number_of_trips=10,
            receipt_amounts=[],
            sheet_pdf=b"%PDF-",
            receipt_pdfs=[],
        )
```

- [ ] **Step 2: Run, must fail**

- [ ] **Step 3: Creare `fdp_app/pathtracks/service.py`**

```python
"""Orchestrazione transazionale per la dichiarazione mensile.

Coordina:
- CoordinateRepo: lookup del punto di partenza attivo
- RateRepo: lookup del rate valido per la data (solo carburante)
- ReimbursementCalculator: calcolo importo
- RegistryRepo: chiamata SP Employee.dbo.Registro
- PathTrackRepo: INSERT della riga
- PathTrackDocRepo: INSERT dei BLOB (foglio + ricevute)

Tutto dentro una transazione pyodbc esplicita (autocommit OFF temporaneo).
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Iterable, Optional, Sequence

from fdp_app.pathtracks.calculator import (
    compute_fuel_reimbursement,
    compute_taxi_reimbursement,
)
from fdp_app.repos.coordinate_repo import CoordinateRepo
from fdp_app.repos.doc_repo import PathTrackDocRepo
from fdp_app.repos.pathtrack_repo import PathTrackRepo
from fdp_app.repos.rate_repo import RateRepo
from fdp_app.repos.registry_repo import RegistryRepo


class NoActiveCoordinateError(Exception):
    """Nessun punto di partenza attivo per il dipendente."""


class NoRateConfiguredError(Exception):
    """Nessun rate configurato per la data."""


class DuplicateDeclarationError(Exception):
    """Esiste gia' una dichiarazione attiva per lo stesso mese."""


class DeadlineClosedError(Exception):
    """Periodo di inserimento chiuso."""


class InvalidInputError(Exception):
    """Input validato lato service rifiutato."""


class PathTrackService:
    def __init__(
        self,
        *,
        coordinate_repo: CoordinateRepo,
        rate_repo: RateRepo,
        registry_repo: RegistryRepo,
        pathtrack_repo: PathTrackRepo,
        doc_repo: PathTrackDocRepo,
        connection_factory: Callable[[], object],
    ) -> None:
        self._coord_repo = coordinate_repo
        self._rate_repo = rate_repo
        self._registry_repo = registry_repo
        self._pathtrack_repo = pathtrack_repo
        self._doc_repo = doc_repo
        self._connection_factory = connection_factory

    def _validate_common(
        self,
        *,
        number_of_trips: int,
        sheet_pdf: Optional[bytes],
        receipt_pdfs: Sequence[bytes],
    ) -> None:
        if not (1 <= number_of_trips <= 31):
            raise InvalidInputError(
                f"viaggi: deve essere tra 1 e 31, ricevuto {number_of_trips}"
            )
        if not sheet_pdf or not sheet_pdf.startswith(b"%PDF-"):
            raise InvalidInputError(
                "foglio di percorso PDF obbligatorio e deve essere un PDF valido"
            )
        for i, pdf in enumerate(receipt_pdfs):
            if not pdf or not pdf.startswith(b"%PDF-"):
                raise InvalidInputError(f"ricevuta {i+1} non e' un PDF valido")

    def _insert_docs(
        self,
        *,
        path_track_id: int,
        sheet_pdf: bytes,
        receipt_pdfs: Sequence[bytes],
        sheet_title_prefix: str,
        receipt_title_prefix: str,
    ) -> None:
        self._doc_repo.insert(
            path_track_id=path_track_id,
            doc_title=sheet_title_prefix,
            pdf_bytes=sheet_pdf,
        )
        for i, pdf in enumerate(receipt_pdfs, start=1):
            self._doc_repo.insert(
                path_track_id=path_track_id,
                doc_title=f"{receipt_title_prefix} {i}",
                pdf_bytes=pdf,
            )

    def create_fuel(
        self,
        *,
        employee_hire_history_id: int,
        full_name: str,
        date_path_track: date,
        number_of_trips: int,
        sheet_pdf: Optional[bytes],
        receipt_pdfs: Sequence[bytes],
        in_behalf_of_id: Optional[int] = None,
    ) -> int:
        self._validate_common(
            number_of_trips=number_of_trips,
            sheet_pdf=sheet_pdf,
            receipt_pdfs=receipt_pdfs,
        )
        if not receipt_pdfs:
            raise InvalidInputError("almeno una ricevuta carburante obbligatoria")

        target_employee_id = in_behalf_of_id or employee_hire_history_id

        coord = self._coord_repo.find_active(target_employee_id)
        if coord is None:
            raise NoActiveCoordinateError(
                f"Nessun punto di partenza attivo per dipendente {target_employee_id}"
            )

        rate = self._rate_repo.find_for_date(date_path_track)
        if rate is None:
            raise NoRateConfiguredError(
                f"Nessun rate configurato per {date_path_track}"
            )

        existing = self._pathtrack_repo.find_active_for_month(
            employee_hire_history_id=target_employee_id,
            date_path_track=date_path_track,
        )
        if existing is not None:
            raise DuplicateDeclarationError(
                f"Esiste gia' una dichiarazione attiva per {date_path_track}"
            )

        amount = compute_fuel_reimbursement(
            road_km_one_way=coord.road_km_to_workplace,
            number_of_trips=number_of_trips,
            avg_consumption_km_l=rate.avg_consumption_km_l,
            avg_fuel_price_eur_l=rate.avg_fuel_price_eur_l,
        )

        conn = self._connection_factory()
        prev_autocommit = getattr(conn, "autocommit", True)
        try:
            conn.autocommit = False
            registry_id = self._registry_repo.generate(issued_by_full_name=full_name)
            new_id = self._pathtrack_repo.insert(
                employee_hire_history_id=employee_hire_history_id,
                registry_id=registry_id,
                date_path_track=date_path_track,
                declarated_path_id=coord.coordinate_id,
                in_behalf_of_id=in_behalf_of_id,
                reimbursement_type="CARBURANTE",
                number_of_trips=number_of_trips,
                road_km=coord.road_km_to_workplace,
                rate_id_used=rate.rate_id,
                taxi_total_eur=None,
                computed_amount_eur=amount,
            )
            self._insert_docs(
                path_track_id=new_id,
                sheet_pdf=sheet_pdf,
                receipt_pdfs=receipt_pdfs,
                sheet_title_prefix=f"Foglio di Percorso {date_path_track:%Y-%m}",
                receipt_title_prefix=f"Ricevuta distributore {date_path_track:%Y-%m}",
            )
            conn.commit()
            return new_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.autocommit = prev_autocommit

    def create_taxi(
        self,
        *,
        employee_hire_history_id: int,
        full_name: str,
        date_path_track: date,
        number_of_trips: int,
        receipt_amounts: Sequence[float],
        sheet_pdf: Optional[bytes],
        receipt_pdfs: Sequence[bytes],
        in_behalf_of_id: Optional[int] = None,
    ) -> int:
        self._validate_common(
            number_of_trips=number_of_trips,
            sheet_pdf=sheet_pdf,
            receipt_pdfs=receipt_pdfs,
        )
        if not receipt_amounts or all(a == 0 for a in receipt_amounts):
            raise InvalidInputError("almeno una ricevuta con importo > 0 obbligatoria")
        if not receipt_pdfs:
            raise InvalidInputError("almeno una ricevuta taxi (PDF) obbligatoria")

        target_employee_id = in_behalf_of_id or employee_hire_history_id

        coord = self._coord_repo.find_active(target_employee_id)
        if coord is None:
            raise NoActiveCoordinateError(
                f"Nessun punto di partenza attivo per dipendente {target_employee_id}"
            )

        existing = self._pathtrack_repo.find_active_for_month(
            employee_hire_history_id=target_employee_id,
            date_path_track=date_path_track,
        )
        if existing is not None:
            raise DuplicateDeclarationError(
                f"Esiste gia' una dichiarazione attiva per {date_path_track}"
            )

        amount = compute_taxi_reimbursement(receipt_amounts)

        conn = self._connection_factory()
        prev_autocommit = getattr(conn, "autocommit", True)
        try:
            conn.autocommit = False
            registry_id = self._registry_repo.generate(issued_by_full_name=full_name)
            new_id = self._pathtrack_repo.insert(
                employee_hire_history_id=employee_hire_history_id,
                registry_id=registry_id,
                date_path_track=date_path_track,
                declarated_path_id=coord.coordinate_id,
                in_behalf_of_id=in_behalf_of_id,
                reimbursement_type="TAXI",
                number_of_trips=number_of_trips,
                road_km=coord.road_km_to_workplace,
                rate_id_used=None,
                taxi_total_eur=amount,
                computed_amount_eur=amount,
            )
            self._insert_docs(
                path_track_id=new_id,
                sheet_pdf=sheet_pdf,
                receipt_pdfs=receipt_pdfs,
                sheet_title_prefix=f"Foglio di Percorso {date_path_track:%Y-%m}",
                receipt_title_prefix=f"Ricevuta taxi {date_path_track:%Y-%m}",
            )
            conn.commit()
            return new_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.autocommit = prev_autocommit

    def delete(
        self, *, path_track_id: int, employee_hire_history_id: int
    ) -> bool:
        return self._pathtrack_repo.soft_delete(
            path_track_id=path_track_id,
            employee_hire_history_id=employee_hire_history_id,
        )

    def list_for_employee(
        self, *, employee_hire_history_id: int
    ):
        return self._pathtrack_repo.list_for_employee(
            employee_hire_history_id=employee_hire_history_id,
        )

    def find_by_id(
        self, *, path_track_id: int, employee_hire_history_id: int
    ):
        return self._pathtrack_repo.find_by_id(
            path_track_id=path_track_id,
            employee_hire_history_id=employee_hire_history_id,
        )
```

- [ ] **Step 4: Run, must pass**

Expected: 9 passed.

- [ ] **Step 5: Full suite**

Expected: 111 passed (102 + 9).

- [ ] **Step 6: Commit**

```bash
git add fdp_app/pathtracks/service.py tests/test_pathtrack_service.py
git commit -m "feat(pathtracks): transactional PathTrackService for monthly declaration"
```

---

# Fase D — UI e routing

## Task 12: Route `GET /pathtracks/new` — form vuoto

**Files:**
- Create: `fdp_app/pathtracks/routes.py`
- Create: `fdp_app/templates/pathtracks/new.html`
- Modify: `fdp_app/__init__.py` (registra blueprint)
- Test: `tests/test_pathtracks_routes.py`

- [ ] **Step 1: Scrivere i primi 3 test (GET)**

```python
"""Test E2E delle route /pathtracks/*."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from freezegun import freeze_time


@pytest.fixture
def mock_coord_repo():
    with patch("fdp_app.pathtracks.routes.CoordinateRepo") as cls:
        instance = MagicMock()
        instance.find_active.return_value = None
        cls.return_value = instance
        yield instance


@pytest.fixture
def mock_rate_repo():
    with patch("fdp_app.pathtracks.routes.RateRepo") as cls:
        instance = MagicMock()
        cls.return_value = instance
        yield instance


@pytest.fixture
def mock_pathtrack_repo():
    with patch("fdp_app.pathtracks.routes.PathTrackRepo") as cls:
        instance = MagicMock()
        instance.find_active_for_month.return_value = None
        instance.list_for_employee.return_value = []
        cls.return_value = instance
        yield instance


@pytest.fixture
def mock_doc_repo():
    with patch("fdp_app.pathtracks.routes.PathTrackDocRepo") as cls:
        instance = MagicMock()
        cls.return_value = instance
        yield instance


@pytest.fixture
def mock_registry_repo():
    with patch("fdp_app.pathtracks.routes.RegistryRepo") as cls:
        instance = MagicMock()
        cls.return_value = instance
        yield instance


def _login(client, eh_id=10):
    with client.session_transaction() as sess:
        sess["user_id"] = eh_id
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = 5
        sess["function_code"] = 70


def test_new_requires_login(client):
    response = client.get("/pathtracks/new", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


@freeze_time("2026-05-03 10:00:00+02:00")
def test_new_redirects_to_coordinates_when_no_active_coordinate(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo
):
    _login(client)
    mock_coord_repo.find_active.return_value = None

    response = client.get("/pathtracks/new", follow_redirects=False)
    assert response.status_code == 302
    assert "/coordinates" in response.headers["Location"]


@freeze_time("2026-05-03 10:00:00+02:00")
def test_new_shows_form_when_in_deadline_window(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo
):
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    from fdp_app.repos.rate_repo import Rate
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(
        coordinate_id=99, label="Casa", lat=45.0, lon=9.0, road_km_to_workplace=10.5,
    )
    mock_rate_repo.find_for_date.return_value = Rate(
        rate_id=3, avg_consumption_km_l=15.0, avg_fuel_price_eur_l=1.7,
    )
    mock_pathtrack_repo.find_active_for_month.return_value = None

    response = client.get("/pathtracks/new")
    assert response.status_code == 200
    assert b"Dichiarazione mensile" in response.data
    assert b"Aprile" in response.data or b"04" in response.data  # month label
    assert b"10.5" in response.data or b"10,5" in response.data  # road_km display


@freeze_time("2026-05-06 00:00:01+02:00")
def test_new_blocks_when_deadline_passed(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo
):
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 10.0)

    response = client.get("/pathtracks/new", follow_redirects=True)
    assert response.status_code == 200
    assert b"chius" in response.data.lower() or b"scadut" in response.data.lower()
```

- [ ] **Step 2: Run, must fail**

- [ ] **Step 3: Creare `fdp_app/pathtracks/routes.py` (minimo per i test GET)**

```python
"""Route per la dichiarazione mensile."""
from __future__ import annotations

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request,
    session, url_for,
)

from fdp_app.auth.decorators import login_required
from fdp_app.pathtracks.deadline import is_open_for_month, previous_month_first_day
from fdp_app.pathtracks.service import (
    DuplicateDeclarationError,
    InvalidInputError,
    NoActiveCoordinateError,
    NoRateConfiguredError,
    PathTrackService,
)
from fdp_app.repos.coordinate_repo import CoordinateRepo
from fdp_app.repos.doc_repo import PathTrackDocRepo
from fdp_app.repos.pathtrack_repo import PathTrackRepo
from fdp_app.repos.rate_repo import RateRepo
from fdp_app.repos.registry_repo import RegistryRepo

bp = Blueprint("pathtracks", __name__, url_prefix="/pathtracks")

_MONTH_NAMES_IT = [
    "", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]


def _build_service() -> PathTrackService:
    db = current_app.config["_db"]
    coord_repo = CoordinateRepo(db)
    rate_repo = RateRepo(db)
    registry_repo = RegistryRepo(db)
    pathtrack_repo = PathTrackRepo(db)
    doc_repo = PathTrackDocRepo(db)
    from fdp_app.db import get_request_db
    return PathTrackService(
        coordinate_repo=coord_repo,
        rate_repo=rate_repo,
        registry_repo=registry_repo,
        pathtrack_repo=pathtrack_repo,
        doc_repo=doc_repo,
        connection_factory=get_request_db,
    )


@bp.route("/new", methods=["GET"])
@login_required
def new():
    coord_repo = CoordinateRepo(current_app.config["_db"])
    coord = coord_repo.find_active(session["user_id"])
    if coord is None:
        flash(
            "Definisci prima il punto di partenza nella mappa.",
            "warning",
        )
        return redirect(url_for("coordinates.index"))

    target_month = previous_month_first_day()
    if not is_open_for_month(target_month):
        flash(
            f"Il periodo di inserimento per {_MONTH_NAMES_IT[target_month.month]} "
            f"{target_month.year} e' chiuso (scadenza superata).",
            "danger",
        )
        return redirect(url_for("dashboard.index"))

    pathtrack_repo = PathTrackRepo(current_app.config["_db"])
    existing = pathtrack_repo.find_active_for_month(
        employee_hire_history_id=session["user_id"],
        date_path_track=target_month,
    )
    if existing is not None:
        return redirect(url_for("pathtracks.view", path_track_id=existing.path_track_id))

    rate_repo = RateRepo(current_app.config["_db"])
    rate = rate_repo.find_for_date(target_month)

    return render_template(
        "pathtracks/new.html",
        target_month=target_month,
        month_label=_MONTH_NAMES_IT[target_month.month],
        coord=coord,
        rate=rate,
    )
```

- [ ] **Step 4: Creare `fdp_app/templates/pathtracks/new.html`** (minimo per i test, sara' esteso in Task 13)

```html
{% extends "base.html" %}
{% block title %}Dichiarazione mensile - Fogli di Percorso{% endblock %}
{% block content %}
<h2>Dichiarazione mensile - {{ month_label }} {{ target_month.year }}</h2>

<div class="card mb-3">
    <div class="card-body">
        <p><strong>Punto di partenza:</strong> {{ coord.label }}</p>
        <p><strong>Distanza stradale (one-way):</strong>
           {{ "%.3f"|format(coord.road_km_to_workplace) }} km</p>
        {% if rate %}
        <p><strong>Rate corrente:</strong>
           {{ rate.avg_consumption_km_l }} km/l - €{{ rate.avg_fuel_price_eur_l }}/l</p>
        {% else %}
        <div class="alert alert-warning">Nessun rate configurato per il mese.</div>
        {% endif %}
    </div>
</div>

<p><em>Task 13 aggiungera' il form di inserimento.</em></p>
{% endblock %}
```

- [ ] **Step 5: Registrare il blueprint in `fdp_app/__init__.py`**

In `_register_blueprints`, aggiungere:

```python
    from fdp_app.pathtracks.routes import bp as pathtracks_bp
    app.register_blueprint(pathtracks_bp)
```

- [ ] **Step 6: Run tests, deve passare**

Expected: 4 passed nel test_pathtracks_routes.py.

- [ ] **Step 7: Full suite**

Expected: 115 passed (111 + 4).

- [ ] **Step 8: Commit**

```bash
git add fdp_app/pathtracks/routes.py fdp_app/templates/pathtracks/ fdp_app/__init__.py tests/test_pathtracks_routes.py
git commit -m "feat(pathtracks): GET /pathtracks/new with deadline and pre-conditions"
```

---

## Task 13: POST `/pathtracks/new` + form completo

**Files:**
- Modify: `fdp_app/pathtracks/routes.py` (add POST handler)
- Modify: `fdp_app/templates/pathtracks/new.html` (full form)
- Create: `fdp_app/static/js/pathtracks.js`
- Modify: `tests/test_pathtracks_routes.py` (add POST tests)

- [ ] **Step 1: Aggiungere test POST**

Aggiungere a `tests/test_pathtracks_routes.py`:

```python
@freeze_time("2026-05-03 10:00:00+02:00")
def test_post_new_fuel_creates_declaration(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo,
    mock_doc_repo, mock_registry_repo
):
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    from fdp_app.repos.rate_repo import Rate
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(
        99, "Casa", 45.0, 9.0, 10.0,
    )
    mock_rate_repo.find_for_date.return_value = Rate(3, 15.0, 1.7)
    mock_pathtrack_repo.find_active_for_month.return_value = None
    mock_pathtrack_repo.insert.return_value = 555
    mock_registry_repo.generate.return_value = 500

    # Mock connection_factory: il service userà get_request_db che in test e' MagicMock
    with patch("fdp_app.pathtracks.routes.get_request_db") as mock_get_db:
        conn = MagicMock()
        conn.autocommit = True
        mock_get_db.return_value = conn

        from io import BytesIO
        response = client.post(
            "/pathtracks/new",
            data={
                "reimbursement_type": "CARBURANTE",
                "number_of_trips": "20",
                "sheet_pdf": (BytesIO(b"%PDF-1.4 sheet"), "foglio.pdf"),
                "receipt_pdf": (BytesIO(b"%PDF-1.4 receipt"), "ricevuta.pdf"),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert "/pathtracks/555" in response.headers["Location"]
    mock_pathtrack_repo.insert.assert_called_once()
    kwargs = mock_pathtrack_repo.insert.call_args.kwargs
    assert kwargs["reimbursement_type"] == "CARBURANTE"
    assert kwargs["number_of_trips"] == 20


@freeze_time("2026-05-03 10:00:00+02:00")
def test_post_new_taxi_creates_declaration(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo,
    mock_doc_repo, mock_registry_repo
):
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(
        99, "Casa", 45.0, 9.0, 10.0,
    )
    mock_pathtrack_repo.find_active_for_month.return_value = None
    mock_pathtrack_repo.insert.return_value = 556
    mock_registry_repo.generate.return_value = 600

    with patch("fdp_app.pathtracks.routes.get_request_db") as mock_get_db:
        conn = MagicMock()
        conn.autocommit = True
        mock_get_db.return_value = conn

        from io import BytesIO
        response = client.post(
            "/pathtracks/new",
            data={
                "reimbursement_type": "TAXI",
                "number_of_trips": "10",
                "taxi_amount": ["12.50", "8.30"],
                "sheet_pdf": (BytesIO(b"%PDF-1.4 sheet"), "foglio.pdf"),
                "receipt_pdf": [
                    (BytesIO(b"%PDF-1.4 r1"), "r1.pdf"),
                    (BytesIO(b"%PDF-1.4 r2"), "r2.pdf"),
                ],
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )

    assert response.status_code == 302
    kwargs = mock_pathtrack_repo.insert.call_args.kwargs
    assert kwargs["reimbursement_type"] == "TAXI"
    assert kwargs["taxi_total_eur"] == pytest.approx(20.80)


@freeze_time("2026-05-03 10:00:00+02:00")
def test_post_new_rejects_missing_sheet_pdf(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo
):
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    from fdp_app.repos.rate_repo import Rate
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 10.0)
    mock_rate_repo.find_for_date.return_value = Rate(3, 15.0, 1.7)
    mock_pathtrack_repo.find_active_for_month.return_value = None

    from io import BytesIO
    response = client.post(
        "/pathtracks/new",
        data={
            "reimbursement_type": "CARBURANTE",
            "number_of_trips": "10",
            "receipt_pdf": (BytesIO(b"%PDF-1.4"), "ricevuta.pdf"),
            # sheet_pdf MANCANTE
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"foglio" in response.data.lower()
    mock_pathtrack_repo.insert.assert_not_called()


@freeze_time("2026-05-03 10:00:00+02:00")
def test_post_new_rejects_oversized_pdf(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo
):
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    from fdp_app.repos.rate_repo import Rate
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 10.0)
    mock_rate_repo.find_for_date.return_value = Rate(3, 15.0, 1.7)
    mock_pathtrack_repo.find_active_for_month.return_value = None

    from io import BytesIO
    big_pdf = b"%PDF-1.4" + (b"\x00" * (5 * 1024 * 1024 + 1))  # > 5 MB

    response = client.post(
        "/pathtracks/new",
        data={
            "reimbursement_type": "CARBURANTE",
            "number_of_trips": "10",
            "sheet_pdf": (BytesIO(big_pdf), "big.pdf"),
            "receipt_pdf": (BytesIO(b"%PDF-1.4"), "r.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"5 mb" in response.data.lower() or b"troppo grande" in response.data.lower()
```

- [ ] **Step 2: Run, must fail**

- [ ] **Step 3: Aggiungere il POST handler in `fdp_app/pathtracks/routes.py`**

Aggiungere import in cima:

```python
from fdp_app.db import get_request_db
```

E aggiungere la route:

```python
@bp.route("/new", methods=["POST"])
@login_required
def create():
    target_month = previous_month_first_day()
    if not is_open_for_month(target_month):
        flash("Periodo di inserimento chiuso.", "danger")
        return redirect(url_for("dashboard.index"))

    reimbursement_type = (request.form.get("reimbursement_type") or "").strip().upper()
    if reimbursement_type not in ("CARBURANTE", "TAXI"):
        flash("Tipo rimborso non valido.", "danger")
        return redirect(url_for("pathtracks.new"))

    try:
        number_of_trips = int(request.form.get("number_of_trips") or "")
    except ValueError:
        flash("Numero viaggi non valido.", "danger")
        return redirect(url_for("pathtracks.new"))

    # File upload: sheet (singolo) + receipts (multipli)
    sheet_file = request.files.get("sheet_pdf")
    receipt_files = request.files.getlist("receipt_pdf")

    max_bytes = current_app.config["_settings_cls"].UPLOAD_MAX_BYTES
    max_files = current_app.config["_settings_cls"].UPLOAD_MAX_FILES_PER_PATHTRACK

    if not sheet_file or not sheet_file.filename:
        flash("Foglio di percorso (PDF) obbligatorio.", "danger")
        return redirect(url_for("pathtracks.new"))
    sheet_bytes = sheet_file.read()
    if len(sheet_bytes) > max_bytes:
        flash(f"Foglio di percorso troppo grande (max 5 MB).", "danger")
        return redirect(url_for("pathtracks.new"))

    receipt_bytes_list = []
    for f in receipt_files:
        if f and f.filename:
            data = f.read()
            if len(data) > max_bytes:
                flash(f"Ricevuta '{f.filename}' troppo grande (max 5 MB).", "danger")
                return redirect(url_for("pathtracks.new"))
            receipt_bytes_list.append(data)

    if not receipt_bytes_list:
        flash("Almeno una ricevuta (PDF) obbligatoria.", "danger")
        return redirect(url_for("pathtracks.new"))

    if len(receipt_bytes_list) + 1 > max_files:  # +1 for sheet
        flash(f"Troppi file caricati (max {max_files}).", "danger")
        return redirect(url_for("pathtracks.new"))

    service = _build_service()

    try:
        if reimbursement_type == "CARBURANTE":
            new_id = service.create_fuel(
                employee_hire_history_id=session["user_id"],
                full_name=session["full_name"],
                date_path_track=target_month,
                number_of_trips=number_of_trips,
                sheet_pdf=sheet_bytes,
                receipt_pdfs=receipt_bytes_list,
            )
        else:  # TAXI
            taxi_amounts_raw = request.form.getlist("taxi_amount")
            try:
                taxi_amounts = [float(a) for a in taxi_amounts_raw if a.strip()]
            except ValueError:
                flash("Importi ricevute non validi.", "danger")
                return redirect(url_for("pathtracks.new"))
            new_id = service.create_taxi(
                employee_hire_history_id=session["user_id"],
                full_name=session["full_name"],
                date_path_track=target_month,
                number_of_trips=number_of_trips,
                receipt_amounts=taxi_amounts,
                sheet_pdf=sheet_bytes,
                receipt_pdfs=receipt_bytes_list,
            )

        current_app.logger.info(
            "PathTrack created: user_id=%s id=%s type=%s",
            session["user_id"], new_id, reimbursement_type,
        )
        flash("Dichiarazione mensile salvata.", "success")
        return redirect(url_for("pathtracks.view", path_track_id=new_id))
    except NoActiveCoordinateError:
        flash("Definisci prima il punto di partenza nella mappa.", "warning")
        return redirect(url_for("coordinates.index"))
    except NoRateConfiguredError:
        current_app.logger.error("No rate configured for %s", target_month)
        flash("Rate non configurato per il mese. Contattare l'amministratore.", "danger")
        return redirect(url_for("pathtracks.new"))
    except DuplicateDeclarationError:
        flash("Esiste gia' una dichiarazione attiva per il mese.", "warning")
        return redirect(url_for("pathtracks.new"))
    except InvalidInputError as e:
        flash(str(e), "danger")
        return redirect(url_for("pathtracks.new"))
```

- [ ] **Step 4: Estendere `fdp_app/templates/pathtracks/new.html`** con il form completo

Sostituire il contenuto (mantieni il blocco header e card-info, sostituisci il commento finale con il form):

```html
{% extends "base.html" %}
{% block title %}Dichiarazione mensile - Fogli di Percorso{% endblock %}
{% block content %}
<h2>Dichiarazione mensile - {{ month_label }} {{ target_month.year }}</h2>

<div class="card mb-3">
    <div class="card-body">
        <p><strong>Punto di partenza:</strong> {{ coord.label }}</p>
        <p><strong>Distanza stradale (one-way):</strong>
           {{ "%.3f"|format(coord.road_km_to_workplace) }} km</p>
        {% if rate %}
        <p><strong>Rate corrente:</strong>
           {{ rate.avg_consumption_km_l }} km/l - €{{ rate.avg_fuel_price_eur_l }}/l</p>
        {% endif %}
    </div>
</div>

<form method="post" enctype="multipart/form-data" id="pathtrack-form">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">

    <div class="mb-3">
        <label class="form-label">Tipo rimborso</label>
        <div class="form-check">
            <input class="form-check-input" type="radio" name="reimbursement_type"
                   id="rt-fuel" value="CARBURANTE" checked>
            <label class="form-check-label" for="rt-fuel">Carburante</label>
        </div>
        <div class="form-check">
            <input class="form-check-input" type="radio" name="reimbursement_type"
                   id="rt-taxi" value="TAXI">
            <label class="form-check-label" for="rt-taxi">Taxi</label>
        </div>
    </div>

    <div class="mb-3">
        <label for="number_of_trips" class="form-label">Numero viaggi (A/R)</label>
        <input type="number" class="form-control" id="number_of_trips"
               name="number_of_trips" min="1" max="31" required>
        <div class="form-text">Il sistema considera ogni viaggio come andata + ritorno.</div>
    </div>

    <div id="taxi-section" style="display:none;">
        <label class="form-label">Importi ricevute (€)</label>
        <div id="taxi-amounts-list">
            <input type="number" class="form-control mb-2" name="taxi_amount"
                   step="0.01" min="0" placeholder="es. 12.50">
        </div>
        <button type="button" class="btn btn-sm btn-outline-secondary mb-3"
                id="add-taxi-amount">+ Aggiungi ricevuta</button>
    </div>

    <div class="mb-3">
        <label for="sheet_pdf" class="form-label">Foglio di percorso (PDF, max 5 MB)</label>
        <input type="file" class="form-control" id="sheet_pdf"
               name="sheet_pdf" accept="application/pdf" required>
    </div>

    <div class="mb-3">
        <label for="receipt_pdf" class="form-label">Ricevute (PDF, max 5 MB ciascuna)</label>
        <input type="file" class="form-control" id="receipt_pdf"
               name="receipt_pdf" accept="application/pdf" multiple required>
    </div>

    <div class="mb-3">
        <strong>Anteprima rimborso:</strong>
        <span id="amount-preview" class="amount-preview">€ -</span>
    </div>

    <button type="submit" class="btn btn-primary">Salva dichiarazione</button>
    <a href="{{ url_for('dashboard.index') }}" class="btn btn-link">Annulla</a>
</form>

<script>
window.FDP_CONTEXT = {
    roadKm: {{ coord.road_km_to_workplace|tojson }},
    rate: {% if rate %}{{ {"km_l": rate.avg_consumption_km_l, "eur_l": rate.avg_fuel_price_eur_l}|tojson }}{% else %}null{% endif %}
};
</script>
<script src="{{ url_for('static', filename='js/pathtracks.js') }}"></script>
{% endblock %}
```

- [ ] **Step 5: Creare `fdp_app/static/js/pathtracks.js`**

```javascript
(function () {
    "use strict";

    var ctx = window.FDP_CONTEXT;

    var rtRadios = document.querySelectorAll('input[name="reimbursement_type"]');
    var taxiSection = document.getElementById("taxi-section");
    var amountPreview = document.getElementById("amount-preview");
    var tripsInput = document.getElementById("number_of_trips");
    var taxiList = document.getElementById("taxi-amounts-list");

    function isFuel() {
        var checked = document.querySelector('input[name="reimbursement_type"]:checked');
        return checked && checked.value === "CARBURANTE";
    }

    function recompute() {
        var trips = parseInt(tripsInput.value, 10);
        if (!trips || trips < 1) {
            amountPreview.textContent = "€ -";
            return;
        }
        var amount;
        if (isFuel()) {
            if (!ctx.rate) {
                amountPreview.textContent = "(rate non configurato)";
                return;
            }
            amount = (ctx.roadKm * 2 * trips) / ctx.rate.km_l * ctx.rate.eur_l;
        } else {
            // Taxi: somma importi
            var inputs = taxiList.querySelectorAll('input[name="taxi_amount"]');
            amount = 0;
            for (var i = 0; i < inputs.length; i++) {
                var v = parseFloat(inputs[i].value);
                if (!isNaN(v)) amount += v;
            }
        }
        amountPreview.textContent = "€ " + amount.toFixed(2);
    }

    function toggleTaxiSection() {
        taxiSection.style.display = isFuel() ? "none" : "block";
        recompute();
    }

    for (var i = 0; i < rtRadios.length; i++) {
        rtRadios[i].addEventListener("change", toggleTaxiSection);
    }
    tripsInput.addEventListener("input", recompute);
    taxiList.addEventListener("input", function (e) {
        if (e.target.name === "taxi_amount") recompute();
    });

    document.getElementById("add-taxi-amount").addEventListener("click", function () {
        var input = document.createElement("input");
        input.type = "number";
        input.className = "form-control mb-2";
        input.name = "taxi_amount";
        input.step = "0.01";
        input.min = "0";
        input.placeholder = "es. 8.30";
        taxiList.appendChild(input);
    });

    toggleTaxiSection();
}());
```

- [ ] **Step 6: Run tests**

```bash
.venv\Scripts\python.exe -m pytest tests/test_pathtracks_routes.py -v
```
Expected: 8 passed (4 GET originali + 4 POST).

- [ ] **Step 7: Full suite**

Expected: 119 passed (115 + 4).

- [ ] **Step 8: Commit**

```bash
git add fdp_app/pathtracks/routes.py fdp_app/templates/pathtracks/new.html fdp_app/static/js/pathtracks.js tests/test_pathtracks_routes.py
git commit -m "feat(pathtracks): POST /pathtracks/new with file upload and validation"
```

---

## Task 14: GET `/pathtracks/<id>` — visualizzazione

**Files:**
- Modify: `fdp_app/pathtracks/routes.py`
- Create: `fdp_app/templates/pathtracks/view.html`
- Modify: `tests/test_pathtracks_routes.py`

- [ ] **Step 1: Aggiungere test view**

```python
def test_view_requires_login(client):
    response = client.get("/pathtracks/1", follow_redirects=False)
    assert response.status_code == 302


def test_view_shows_declaration(client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo):
    from fdp_app.repos.pathtrack_repo import PathTrackRow
    from datetime import date as Date
    _login(client)
    mock_pathtrack_repo.find_by_id.return_value = PathTrackRow(
        path_track_id=100, registry_id=500, date_path_track=Date(2026, 4, 1),
        declarated_path_id=99, in_behalf_of_id=None,
        reimbursement_type="CARBURANTE", number_of_trips=20, road_km=10.0,
        rate_id_used=3, taxi_total_eur=None, computed_amount_eur=45.33,
    )
    mock_doc_repo.list_for_pathtrack.return_value = []

    response = client.get("/pathtracks/100")
    assert response.status_code == 200
    assert b"CARBURANTE" in response.data
    assert b"45.33" in response.data or b"45,33" in response.data
    assert b"Aprile" in response.data


def test_view_not_owned_returns_404(client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo):
    _login(client)
    mock_pathtrack_repo.find_by_id.return_value = None

    response = client.get("/pathtracks/999")
    assert response.status_code == 404
```

- [ ] **Step 2: Aggiungere il view handler in `fdp_app/pathtracks/routes.py`**

```python
@bp.route("/<int:path_track_id>", methods=["GET"])
@login_required
def view(path_track_id: int):
    pathtrack_repo = PathTrackRepo(current_app.config["_db"])
    row = pathtrack_repo.find_by_id(
        path_track_id=path_track_id,
        employee_hire_history_id=session["user_id"],
    )
    if row is None:
        from flask import abort
        abort(404)
    doc_repo = PathTrackDocRepo(current_app.config["_db"])
    docs = doc_repo.list_for_pathtrack(path_track_id=path_track_id)

    target_month = row.date_path_track
    can_edit = is_open_for_month(target_month)
    return render_template(
        "pathtracks/view.html",
        row=row,
        docs=docs,
        month_label=_MONTH_NAMES_IT[target_month.month],
        can_edit=can_edit,
    )
```

- [ ] **Step 3: Creare `fdp_app/templates/pathtracks/view.html`**

```html
{% extends "base.html" %}
{% block title %}Dichiarazione #{{ row.path_track_id }} - Fogli di Percorso{% endblock %}
{% block content %}
<h2>Dichiarazione - {{ month_label }} {{ row.date_path_track.year }}</h2>

<table class="table">
    <tbody>
        <tr><th>Numero registro</th><td>{{ row.registry_id }}</td></tr>
        <tr><th>Tipo rimborso</th><td>{{ row.reimbursement_type }}</td></tr>
        <tr><th>Numero viaggi A/R</th><td>{{ row.number_of_trips }}</td></tr>
        <tr><th>Distanza one-way</th><td>{{ "%.3f"|format(row.road_km) }} km</td></tr>
        {% if row.taxi_total_eur is not none %}
        <tr><th>Totale taxi (ricevute)</th><td>€ {{ "%.2f"|format(row.taxi_total_eur) }}</td></tr>
        {% endif %}
        <tr><th>Importo rimborso</th><td><strong>€ {{ "%.2f"|format(row.computed_amount_eur) }}</strong></td></tr>
    </tbody>
</table>

<h4>Documenti</h4>
{% if docs %}
<ul class="list-group mb-3">
    {% for doc in docs %}
    <li class="list-group-item">
        <a href="{{ url_for('pathtracks.download_doc', doc_id=doc.doc_id) }}">{{ doc.doc_title }}</a>
    </li>
    {% endfor %}
</ul>
{% else %}
<p class="text-muted">Nessun documento.</p>
{% endif %}

{% if can_edit %}
<form action="{{ url_for('pathtracks.delete', path_track_id=row.path_track_id) }}"
      method="post" class="d-inline">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <button type="submit" class="btn btn-outline-danger"
            onclick="return confirm('Cancellare la dichiarazione?');">
        Cancella
    </button>
</form>
{% else %}
<p class="text-muted"><em>Periodo di modifica chiuso (oltre il 5 del mese successivo).</em></p>
{% endif %}

<a href="{{ url_for('pathtracks.list_mine') }}" class="btn btn-link">Torna alla lista</a>
{% endblock %}
```

- [ ] **Step 4: Aggiungere route download_doc (per i link nel template)**

```python
@bp.route("/docs/<int:doc_id>/download", methods=["GET"])
@login_required
def download_doc(doc_id: int):
    from flask import abort, Response
    doc_repo = PathTrackDocRepo(current_app.config["_db"])
    pathtrack_repo = PathTrackRepo(current_app.config["_db"])
    try:
        pdf_bytes, title = doc_repo.get_blob(doc_id=doc_id)
    except FileNotFoundError:
        abort(404)

    # Verifica ownership: il doc deve appartenere a un pathtrack del session user
    # (sicurezza orizzontale)
    docs = doc_repo.list_for_pathtrack(path_track_id=-1)  # placeholder
    # In modo piu' efficiente: facciamo una query check
    # Per semplicita': l'app ha gia' verificato che find_by_id ritorna None se non owned,
    # ma get_blob non sa di chi e'. Aggiungiamo una query check.
    # NOTA: il check piu' robusto e' una JOIN; qui usiamo la list_for_pathtrack
    # con il pathtrack_id che e' embedded in get_blob in V1.
    # Implementazione semplificata: list i docs propri e verifica appartenenza.
    own_path_tracks = pathtrack_repo.list_for_employee(
        employee_hire_history_id=session["user_id"]
    )
    own_doc_ids = set()
    for pt in own_path_tracks:
        for d in doc_repo.list_for_pathtrack(path_track_id=pt.path_track_id):
            own_doc_ids.add(d.doc_id)
    if doc_id not in own_doc_ids:
        abort(404)

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{title}.pdf"'},
    )
```

Nota: questo check ownership è O(n × m) (poco efficiente). In Piano 4 sarà rifattorizzato con una query SQL JOIN diretta. Per V1 di Piano 3 è sufficiente.

- [ ] **Step 5: Run tests**

Expected: 11 passed (8 + 3 nuovi).

- [ ] **Step 6: Full suite**

Expected: 122 passed.

- [ ] **Step 7: Commit**

```bash
git add fdp_app/pathtracks/routes.py fdp_app/templates/pathtracks/view.html tests/test_pathtracks_routes.py
git commit -m "feat(pathtracks): GET view + PDF download with ownership check"
```

---

## Task 15: POST `/pathtracks/<id>/delete` — soft delete entro scadenza

**Files:**
- Modify: `fdp_app/pathtracks/routes.py`
- Modify: `tests/test_pathtracks_routes.py`

- [ ] **Step 1: Aggiungere test delete**

```python
@freeze_time("2026-05-03 10:00:00+02:00")
def test_post_delete_soft_deletes_within_window(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo
):
    from fdp_app.repos.pathtrack_repo import PathTrackRow
    from datetime import date as Date
    _login(client)
    mock_pathtrack_repo.find_by_id.return_value = PathTrackRow(
        path_track_id=100, registry_id=500, date_path_track=Date(2026, 4, 1),
        declarated_path_id=99, in_behalf_of_id=None,
        reimbursement_type="CARBURANTE", number_of_trips=10, road_km=10.0,
        rate_id_used=3, taxi_total_eur=None, computed_amount_eur=10.0,
    )
    mock_pathtrack_repo.soft_delete.return_value = True

    response = client.post(
        "/pathtracks/100/delete",
        follow_redirects=False,
    )

    assert response.status_code == 302
    mock_pathtrack_repo.soft_delete.assert_called_once_with(
        path_track_id=100, employee_hire_history_id=10
    )


@freeze_time("2026-05-06 00:00:01+02:00")
def test_post_delete_rejects_after_window(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo
):
    from fdp_app.repos.pathtrack_repo import PathTrackRow
    from datetime import date as Date
    _login(client)
    mock_pathtrack_repo.find_by_id.return_value = PathTrackRow(
        path_track_id=100, registry_id=500, date_path_track=Date(2026, 4, 1),
        declarated_path_id=99, in_behalf_of_id=None,
        reimbursement_type="CARBURANTE", number_of_trips=10, road_km=10.0,
        rate_id_used=3, taxi_total_eur=None, computed_amount_eur=10.0,
    )

    response = client.post(
        "/pathtracks/100/delete",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"chius" in response.data.lower() or b"scadut" in response.data.lower()
    mock_pathtrack_repo.soft_delete.assert_not_called()
```

- [ ] **Step 2: Aggiungere il delete handler**

```python
@bp.route("/<int:path_track_id>/delete", methods=["POST"])
@login_required
def delete(path_track_id: int):
    pathtrack_repo = PathTrackRepo(current_app.config["_db"])
    row = pathtrack_repo.find_by_id(
        path_track_id=path_track_id,
        employee_hire_history_id=session["user_id"],
    )
    if row is None:
        from flask import abort
        abort(404)

    if not is_open_for_month(row.date_path_track):
        flash("Periodo di modifica chiuso. Cancellazione non consentita.", "danger")
        return redirect(url_for("pathtracks.view", path_track_id=path_track_id))

    ok = pathtrack_repo.soft_delete(
        path_track_id=path_track_id,
        employee_hire_history_id=session["user_id"],
    )
    if ok:
        # Cancella anche i documenti
        doc_repo = PathTrackDocRepo(current_app.config["_db"])
        doc_repo.soft_delete_all_for_pathtrack(path_track_id=path_track_id)
        current_app.logger.info(
            "PathTrack deleted: user_id=%s id=%s", session["user_id"], path_track_id
        )
        flash("Dichiarazione cancellata.", "success")
    else:
        flash("Impossibile cancellare (record non trovato o gia' cancellato).", "warning")
    return redirect(url_for("pathtracks.list_mine"))
```

- [ ] **Step 3: Run tests + full suite**

Expected: 13 in test_pathtracks_routes.py, 124 total.

- [ ] **Step 4: Commit**

```bash
git add fdp_app/pathtracks/routes.py tests/test_pathtracks_routes.py
git commit -m "feat(pathtracks): POST delete with deadline check"
```

---

## Task 16: GET `/pathtracks` — storico personale

**Files:**
- Modify: `fdp_app/pathtracks/routes.py`
- Create: `fdp_app/templates/pathtracks/list.html`
- Modify: `tests/test_pathtracks_routes.py`

- [ ] **Step 1: Aggiungere test list**

```python
def test_list_shows_user_declarations(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo
):
    from fdp_app.repos.pathtrack_repo import PathTrackRow
    from datetime import date as Date
    _login(client)
    mock_pathtrack_repo.list_for_employee.return_value = [
        PathTrackRow(1, 100, Date(2026, 4, 1), 99, None, "CARBURANTE", 20, 10.0, 3, None, 45.33),
        PathTrackRow(2, 101, Date(2026, 3, 1), 99, None, "TAXI", 10, 8.0, None, 30.0, 30.0),
    ]

    response = client.get("/pathtracks")
    assert response.status_code == 200
    assert b"CARBURANTE" in response.data
    assert b"TAXI" in response.data
    assert b"45.33" in response.data or b"45,33" in response.data
```

- [ ] **Step 2: Aggiungere il list handler**

```python
@bp.route("", methods=["GET"])
@login_required
def list_mine():
    pathtrack_repo = PathTrackRepo(current_app.config["_db"])
    rows = pathtrack_repo.list_for_employee(
        employee_hire_history_id=session["user_id"],
    )
    return render_template(
        "pathtracks/list.html",
        rows=rows,
        month_names=_MONTH_NAMES_IT,
    )
```

- [ ] **Step 3: Creare `fdp_app/templates/pathtracks/list.html`**

```html
{% extends "base.html" %}
{% block title %}Le mie dichiarazioni - Fogli di Percorso{% endblock %}
{% block content %}
<h2>Le mie dichiarazioni</h2>

<a href="{{ url_for('pathtracks.new') }}" class="btn btn-primary mb-3">Nuova dichiarazione</a>

{% if rows %}
<table class="table table-striped">
    <thead>
        <tr>
            <th>Mese</th>
            <th>Tipo</th>
            <th>Viaggi A/R</th>
            <th>Importo</th>
            <th>N. registro</th>
            <th></th>
        </tr>
    </thead>
    <tbody>
        {% for row in rows %}
        <tr>
            <td>{{ month_names[row.date_path_track.month] }} {{ row.date_path_track.year }}</td>
            <td>{{ row.reimbursement_type }}</td>
            <td>{{ row.number_of_trips }}</td>
            <td>€ {{ "%.2f"|format(row.computed_amount_eur) }}</td>
            <td>{{ row.registry_id }}</td>
            <td>
                <a href="{{ url_for('pathtracks.view', path_track_id=row.path_track_id) }}"
                   class="btn btn-sm btn-outline-primary">Dettagli</a>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% else %}
<div class="alert alert-info">Nessuna dichiarazione presente.</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 4: Run tests + full suite**

Expected: 14 in test_pathtracks_routes.py, 125 total.

- [ ] **Step 5: Commit**

```bash
git add fdp_app/pathtracks/routes.py fdp_app/templates/pathtracks/list.html tests/test_pathtracks_routes.py
git commit -m "feat(pathtracks): GET /pathtracks personal history list"
```

---

## Task 17: Attivare dashboard card "Dichiarazione mensile"

**Files:**
- Modify: `fdp_app/templates/dashboard/index.html`
- Modify: `tests/test_dashboard.py`

- [ ] **Step 1: Modificare la card**

Trova:
```html
<a class="btn btn-outline-primary disabled" href="#">Disponibile nel Piano 3</a>
```
(quella nella card "Dichiarazione mensile")

Sostituisci con:
```html
<a class="btn btn-outline-primary" href="{{ url_for('pathtracks.list_mine') }}">Vai alle dichiarazioni</a>
```

- [ ] **Step 2: Aggiungere test**

```python
def test_dashboard_card_links_to_pathtracks(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = 7
        sess["function_code"] = 65

    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"/pathtracks" in response.data
    assert b"Disponibile nel Piano 3" not in response.data
```

- [ ] **Step 3: Run + full suite**

Expected: 126 total.

- [ ] **Step 4: Commit**

```bash
git add fdp_app/templates/dashboard/index.html tests/test_dashboard.py
git commit -m "feat(dashboard): activate Dichiarazione mensile card with link"
```

---

## Task 18: Edge case — file PDF magic bytes check

**Files:**
- Modify: `fdp_app/pathtracks/routes.py`
- Modify: `tests/test_pathtracks_routes.py`

- [ ] **Step 1: Aggiungere test**

```python
@freeze_time("2026-05-03 10:00:00+02:00")
def test_post_new_rejects_non_pdf_sheet(
    client, mock_coord_repo, mock_rate_repo, mock_pathtrack_repo, mock_doc_repo, mock_registry_repo
):
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    from fdp_app.repos.rate_repo import Rate
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(99, "x", 1, 2, 10.0)
    mock_rate_repo.find_for_date.return_value = Rate(3, 15.0, 1.7)
    mock_pathtrack_repo.find_active_for_month.return_value = None

    from io import BytesIO
    response = client.post(
        "/pathtracks/new",
        data={
            "reimbursement_type": "CARBURANTE",
            "number_of_trips": "10",
            "sheet_pdf": (BytesIO(b"<html>not a pdf</html>"), "fake.pdf"),
            "receipt_pdf": (BytesIO(b"%PDF-1.4 r"), "r.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    # Validazione magic bytes lato service alza InvalidInputError
    assert b"pdf" in response.data.lower()
    mock_pathtrack_repo.insert.assert_not_called()
```

- [ ] **Step 2: Verifica che il service intercetti gia' i magic bytes**

Il `_validate_common` nel service controlla `sheet_pdf.startswith(b"%PDF-")`. Quindi questo test dovrebbe gia' passare. Run:

```bash
.venv\Scripts\python.exe -m pytest tests/test_pathtracks_routes.py::test_post_new_rejects_non_pdf_sheet -v
```

Se passa direttamente, perfetto. Se fallisce per un motivo HTTP-level, aggiungere un early-check nel route:

```python
    # In create(), prima di chiamare il service, dopo aver letto sheet_bytes:
    if not sheet_bytes.startswith(b"%PDF-"):
        flash("Il foglio di percorso non e' un PDF valido.", "danger")
        return redirect(url_for("pathtracks.new"))
```

- [ ] **Step 3: Run + full suite**

Expected: 127 total.

- [ ] **Step 4: Commit**

```bash
git add fdp_app/pathtracks/routes.py tests/test_pathtracks_routes.py
git commit -m "feat(pathtracks): explicit PDF magic-bytes validation in route"
```

---

# Fase E — Smoke test

## Task 19: Smoke test manuale + tag `v0.3.0-pathtracks`

**Files:** nessuno.

- [ ] **Step 1: Eseguire la suite completa**

```bash
.venv\Scripts\python.exe -m pytest -v
```
Expected: tutti i test verdi (~127).

- [ ] **Step 2: Verificare il DB di staging**

Eseguire in SSMS:
```sql
-- Conferma che la SP Employee.dbo.Registro esiste
SELECT name FROM sys.procedures WHERE name = 'Registro';

-- Conferma che la tabella PathTrackReimbursementRates ha almeno una riga valida per oggi
SELECT TOP 1 RateId, AvgConsumptionKmL, AvgFuelPriceEurL, ValidFrom, ValidTo
FROM Employee.fdp.PathTrackReimbursementRates
WHERE ValidFrom <= CAST(GETDATE() AS DATE)
  AND (ValidTo IS NULL OR ValidTo >= CAST(GETDATE() AS DATE))
ORDER BY ValidFrom DESC;
```

- [ ] **Step 3: Avviare l'app e fare il login**

```bash
flask --app app run
```
Browser su `http://127.0.0.1:5010/login`. Login con utente FC>60 che ha un punto di partenza attivo.

- [ ] **Step 4: Test flusso end-to-end CARBURANTE**

1. Click sulla card "Dichiarazione mensile" → /pathtracks
2. Click "Nuova dichiarazione" → /pathtracks/new
3. Verificare card-info: punto di partenza + rate corrente
4. Selezionare "Carburante", inserire numero viaggi (es. 20)
5. Caricare un PDF qualsiasi come foglio di percorso (es. un PDF generato dal computer)
6. Caricare 1-2 PDF come ricevute
7. Click "Salva dichiarazione"
8. Atteso: redirect a /pathtracks/<id>, flash success, table con i dati.

Verificare nel DB:
```sql
SELECT TOP 1 * FROM Employee.fdp.PathTracks
WHERE EmployeeHireHistoryId = <tuo_id>
ORDER BY DateSys DESC;
SELECT * FROM Employee.fdp.PathTrackDocs
WHERE PathTrackId = <new_id>;
```
Atteso: riga in PathTracks con ComputedAmountEur, ReceivedOn=NULL, RegistryId valorizzato; 2-3 BLOB in PathTrackDocs.

- [ ] **Step 5: Test flusso TAXI**

1. Cancella la dichiarazione appena creata.
2. Nuova dichiarazione con tipo "TAXI"
3. Compila 2 ricevute (es. 12.50, 8.30)
4. Carica foglio + 2 ricevute PDF
5. Salva
6. Verifica importo = 20.80, TaxiTotalEur valorizzato, RateIdUsed NULL

- [ ] **Step 6: Test cancellazione**

Dalla /pathtracks/<id>, click "Cancella". Atteso: redirect a /pathtracks, riga sparita dalla lista, DateOut valorizzato nel DB.

- [ ] **Step 7: Test scadenza (manualmente)**

Modificare temporaneamente `previous_month_first_day()` in `deadline.py` per restituire `date(2026, 3, 1)` (oltre scadenza). Riavvia app. Atteso: /pathtracks/new → flash "Periodo chiuso", redirect.
**Importante**: ripristinare il codice originale al termine del test.

- [ ] **Step 8: Tag**

```bash
git tag -a v0.3.0-pathtracks -m "Piano 3 - Dichiarazione mensile completato

Phase A - Piano 2 follow-up fixes:
- flask.g per-request DB connection (remove threading.Lock)
- RoutingClient + workplace cached in app.config
- Test cleanup (rename + rewrite vacuous test)

Phase B - Foundation:
- RateRepo (PathTrackReimbursementRates lookup)
- RegistryRepo (Employee.dbo.Registro SP call)
- ReimbursementCalculator (fuel + taxi, ROUND_HALF_UP)
- DeadlineService (Europe/Rome timezone)

Phase C - Persistence:
- PathTrackRepo (CRUD + list)
- PathTrackDocRepo (BLOB storage)
- PathTrackService (transactional orchestration with rollback)

Phase D - UI:
- /pathtracks/new GET + POST (form, file upload, validation)
- /pathtracks/<id> view (with PDF download)
- /pathtracks/<id>/delete (soft delete within window)
- /pathtracks (personal history)
- Dashboard card activated

~127 tests passing.

Follow-ups for Piano 4:
- Ownership check on /pathtracks/docs/<id>/download is O(n*m) - use SQL JOIN
- In-behalf-of support (admin/representante) - Piano 4
- Edit existing declaration (currently only create + delete) - optional Piano 3.x
- TaxiTotalEur could be a separate column rather than === ComputedAmountEur
"
```

- [ ] **Step 9: Push (quando rete disponibile)**

```bash
git push origin main
git push origin v0.3.0-pathtracks
```

---

## Definition of Done — Piano 3

- [x] `flask.g` per-request DB connection (no più threading.Lock)
- [x] `RoutingClient` istanziato a startup (cache funzionante)
- [x] `RateRepo`, `RegistryRepo`, `PathTrackRepo`, `PathTrackDocRepo`
- [x] `ReimbursementCalculator` (carburante + taxi)
- [x] `DeadlineService` (Europe/Rome)
- [x] `PathTrackService` con transazione manuale (commit/rollback)
- [x] /pathtracks/new GET+POST con upload PDF, validazione PDF magic bytes + dimensione
- [x] /pathtracks/<id> view con table + download PDF
- [x] /pathtracks/<id>/delete soft delete
- [x] /pathtracks personal history list
- [x] Dashboard card attivata
- [x] ~127 test verdi
- [x] Smoke test E2E completato
- [x] Tag `v0.3.0-pathtracks` creato

## Prossimi piani

- **Piano 4 — Admin** (representable, history scope SubCdcId, export XLSX, fix ownership-check del PDF download)
- **Piano 5 — Notifiche & scheduler** (CLI send-reminders, close-month, Windows Task Scheduler)
