# Fogli di Percorso — Piano 2: Punto di partenza

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettere a un utente autenticato di registrare e gestire il proprio punto di partenza geografico, calcolare la distanza stradale verso il luogo di lavoro tramite OSRM (con fallback ORS), e visualizzare il tutto su una mappa Leaflet cliccabile.

**Architecture:** Blueprint `coordinates` con service+repo per `fdp.PathTrackCoordinates`. Routing distanze via client HTTP (`fdp_app/pathtracks/routing.py`) verso OSRM pubblico, fallback OpenRouteService. Mappa Leaflet via CDN nei template; geocoding inverso lato browser via Nominatim. Persistenza tramite SQL Server `geography::Point` e soft delete `DateOut`.

**Tech Stack:** Flask 3.x, pyodbc, requests (per OSRM/ORS/Nominatim server-side test mocking via `responses`), Leaflet 1.9 + OpenStreetMap (browser-only), Nominatim (browser-only reverse geocoding).

**Riferimento spec:** `docs/superpowers/specs/2026-05-17-fogli-di-percorso-design.md` (sezioni 5.2, 6.2, 7.5)

**Prerequisito:** Piano 1 completato e taggato `v0.1.0-fondamenta`.

---

## Struttura del Piano

- **Fase A** (Task 1-5): Pre-fixes dal final review del Piano 1.
- **Fase B** (Task 6-13): Implementazione della feature.
- **Fase C** (Task 14): Smoke test manuale + tag `v0.2.0-coordinate`.

---

## File Structure

**File creati:**
- `fdp_app/coordinates/__init__.py`
- `fdp_app/coordinates/service.py` — orchestrazione (verifica esistenza punto attivo, chiama routing, persiste)
- `fdp_app/coordinates/routes.py` — `/coordinates` GET (mappa), POST (save), POST (delete)
- `fdp_app/coordinates/templates/coordinates/index.html` — pagina mappa
- `fdp_app/static/js/coordinates.js` — interazione Leaflet + Nominatim reverse
- `fdp_app/pathtracks/__init__.py`
- `fdp_app/pathtracks/routing.py` — client OSRM/ORS con cache in-process
- `fdp_app/repos/coordinate_repo.py` — CRUD `PathTrackCoordinates` (uso `geography::Point`)
- `tests/test_routing.py` — test client OSRM/ORS con `responses`
- `tests/test_coordinate_repo.py` — test repo con mock cursor
- `tests/test_coordinates_service.py` — test service con mocks
- `tests/test_coordinates_routes.py` — E2E con Flask test_client
- `scripts/set_workplace.py` — script interattivo per aggiornare `workplace.json`

**File modificati:**
- `tests/conftest.py` — teardown logging handlers, registra blueprint coordinates
- `.gitignore` — aggiunge `.env`, `*.env`
- `fdp_app/__init__.py` — warning su `FDP_SECRET_KEY` mancante, registra blueprint coordinates
- `fdp_app/db.py` — `threading.Lock` su `cursor()` (mitigazione thread safety)
- `fdp_app/auth/routes.py` — logout passa a `POST`
- `fdp_app/templates/base.html` — link logout diventa `<form method="post">` con CSRF
- `fdp_app/templates/dashboard/index.html` — card "Punto di partenza" diventa attiva (link a `/coordinates`)
- `config/workplace.json` — coordinate reali (operativo, fatto dall'utente via script)

---

# Fase A — Pre-fixes Piano 1

## Task 1: `.gitignore` — proteggere file `.env` e teardown logging fixtures

**Files:**
- Modify: `.gitignore`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Aggiornare `.gitignore`**

Leggere il file, aggiungere subito sotto la sezione "Secret files (existing)" queste due righe:

```
.env
*.env
```

Lasciare `.flaskenv` non ignorato (è già fuori dal pattern `.env` perché git tratta `.flaskenv` come letterale, non come `.<anything>.env`).

- [ ] **Step 2: Verificare che `.flaskenv` resta tracciato**

```bash
git check-ignore .flaskenv
```
Expected: **no output** (significa che NON è ignorato — è quello che vogliamo).

```bash
git check-ignore .env
git check-ignore foo.env
```
Expected: stampa il path stesso (significa che SAREBBE ignorato — è quello che vogliamo).

- [ ] **Step 3: Aggiungere teardown logging in `tests/conftest.py`**

Aprire `tests/conftest.py` e sostituire la fixture `app`:

DA:
```python
@pytest.fixture
def app(mock_db):
    app = create_app(settings=TestSettings, db=mock_db)
    yield app
```

A:
```python
@pytest.fixture
def app(mock_db):
    application = create_app(settings=TestSettings, db=mock_db)
    yield application
    # Chiude i file handler attaccati a app.logger per evitare leak
    for handler in list(application.logger.handlers):
        try:
            handler.close()
        except Exception:
            pass
        application.logger.removeHandler(handler)
```

- [ ] **Step 4: Eseguire i test, devono passare**

```bash
.venv\Scripts\python.exe -m pytest -q
```
Expected: `30 passed`.

- [ ] **Step 5: Commit**

```bash
git add .gitignore tests/conftest.py
git commit -m "fix: ignore .env files and close logging handlers in test teardown"
```

---

## Task 2: Warning su `FDP_SECRET_KEY` mancante in produzione

**Files:**
- Modify: `fdp_app/__init__.py`
- Test: `tests/test_secret_key_warning.py` (nuovo)

- [ ] **Step 1: Scrivere il test**

Creare `tests/test_secret_key_warning.py`:

```python
"""Verifica che l'app emetta un warning se FDP_SECRET_KEY non e' settata in produzione."""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from config.settings import Settings
from fdp_app import create_app
from fdp_app.db import Database


def test_no_warning_when_secret_key_env_var_set(monkeypatch, caplog):
    monkeypatch.setenv("FDP_SECRET_KEY", "explicit-key-from-env-very-long-string-1234567890")
    monkeypatch.delenv("TESTING", raising=False)

    # Forziamo Settings a rileggere SECRET_KEY (era valutato al class-body load)
    class ProdSettings(Settings):
        TESTING = False
        SECRET_KEY = os.environ.get("FDP_SECRET_KEY") or "fallback"

    with caplog.at_level("WARNING"):
        create_app(settings=ProdSettings, db=MagicMock(spec=Database))

    assert "FDP_SECRET_KEY" not in caplog.text


def test_warning_emitted_when_secret_key_env_var_missing(monkeypatch, caplog):
    monkeypatch.delenv("FDP_SECRET_KEY", raising=False)

    class ProdSettings(Settings):
        TESTING = False
        # Simula il fallback: nessuna env var -> chiave ephemeral
        SECRET_KEY = "ephemeral-fallback-do-not-use-in-prod"

    with caplog.at_level("WARNING"):
        create_app(settings=ProdSettings, db=MagicMock(spec=Database))

    assert "FDP_SECRET_KEY" in caplog.text
    assert "non e' impostata" in caplog.text.lower() or "not set" in caplog.text.lower()


def test_no_warning_in_testing_mode(monkeypatch, caplog, app):
    """In TESTING mode il warning e' silenziato (la fixture app usa TestSettings)."""
    # `app` fixture gia' costruisce l'app con TestSettings(TESTING=True)
    # Verifichiamo che NON abbia loggato il warning
    assert "FDP_SECRET_KEY" not in caplog.text
```

- [ ] **Step 2: Eseguire il test, deve fallire**

```bash
.venv\Scripts\python.exe -m pytest tests/test_secret_key_warning.py -v
```
Expected: 2 failures (i due nuovi test sopra; il terzo passa per default).

- [ ] **Step 3: Aggiungere il warning in `fdp_app/__init__.py`**

Localizzare la funzione `create_app` e, subito dopo `csrf.init_app(app)`, aggiungere:

```python
    _warn_if_missing_secret_key(app)
```

Aggiungere la funzione privata vicina alle altre `_register_*`:

```python
def _warn_if_missing_secret_key(app: Flask) -> None:
    """In produzione (TESTING=False) avverte se FDP_SECRET_KEY non e' settata."""
    import os
    if app.config.get("TESTING"):
        return
    if not os.environ.get("FDP_SECRET_KEY"):
        app.logger.warning(
            "FDP_SECRET_KEY env var non e' impostata. "
            "La SECRET_KEY corrente e' ephemeral: a ogni restart le sessioni "
            "esistenti saranno invalidate. Impostare FDP_SECRET_KEY in produzione."
        )
```

- [ ] **Step 4: Eseguire il test, deve passare**

```bash
.venv\Scripts\python.exe -m pytest tests/test_secret_key_warning.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Eseguire tutta la suite**

```bash
.venv\Scripts\python.exe -m pytest -q
```
Expected: 33 passed (30 originali + 3 nuovi).

- [ ] **Step 6: Commit**

```bash
git add fdp_app/__init__.py tests/test_secret_key_warning.py
git commit -m "feat(app): warn at startup if FDP_SECRET_KEY env var is missing"
```

---

## Task 3: Logout GET → POST con CSRF

**Files:**
- Modify: `fdp_app/auth/routes.py`
- Modify: `fdp_app/templates/base.html`
- Modify: `tests/test_auth_routes.py`

- [ ] **Step 1: Aggiornare il test in `tests/test_auth_routes.py`**

Sostituire `test_logout_clears_session_and_redirects` con:

```python
def test_logout_via_get_is_405_method_not_allowed(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 99
    response = client.get("/logout")
    assert response.status_code == 405


def test_logout_via_post_clears_session_and_redirects(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 99
        sess["full_name"] = "Test User"
    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    with client.session_transaction() as sess:
        assert "user_id" not in sess
```

- [ ] **Step 2: Eseguire i test, devono fallire**

```bash
.venv\Scripts\python.exe -m pytest tests/test_auth_routes.py::test_logout_via_get_is_405_method_not_allowed tests/test_auth_routes.py::test_logout_via_post_clears_session_and_redirects -v
```
Expected: 2 failures (logout attualmente accetta GET).

- [ ] **Step 3: Modificare `fdp_app/auth/routes.py`**

Trovare la route `/logout` e cambiare il decoratore:

DA:
```python
@bp.route("/logout")
def logout():
```

A:
```python
@bp.route("/logout", methods=["POST"])
def logout():
```

Il resto della funzione resta invariato.

- [ ] **Step 4: Modificare `fdp_app/templates/base.html`**

Cercare nella navbar:

```html
<a class="btn btn-outline-light btn-sm" href="{{ url_for('auth.logout') }}">Esci</a>
```

Sostituire con un mini-form POST con CSRF token:

```html
<form action="{{ url_for('auth.logout') }}" method="post" class="d-inline">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <button type="submit" class="btn btn-outline-light btn-sm">Esci</button>
</form>
```

- [ ] **Step 5: Eseguire i test**

```bash
.venv\Scripts\python.exe -m pytest tests/test_auth_routes.py -v
```
Expected: 8 passed (i 7 originali aggiornati + 1 nuovo per il 405).

- [ ] **Step 6: Eseguire tutta la suite**

```bash
.venv\Scripts\python.exe -m pytest -q
```
Expected: 34 passed.

- [ ] **Step 7: Commit**

```bash
git add fdp_app/auth/routes.py fdp_app/templates/base.html tests/test_auth_routes.py
git commit -m "fix(auth): require POST + CSRF token for /logout"
```

---

## Task 4: `threading.Lock` su `Database.cursor()` per thread safety

**Files:**
- Modify: `fdp_app/db.py`
- Modify: `tests/test_db_lock.py` (nuovo)

- [ ] **Step 1: Scrivere il test**

Creare `tests/test_db_lock.py`:

```python
"""Verifica che Database.cursor() sia thread-safe rispetto alla connessione condivisa."""
from __future__ import annotations

import threading
from unittest.mock import MagicMock

from fdp_app.db import Database


def test_cursor_lock_serializes_access_to_underlying_connection():
    """Due thread che chiamano cursor() in parallelo non devono vedere
    chiamate sovrapposte a connect()."""
    db = Database.__new__(Database)  # bypass __init__
    db._cm = MagicMock()
    db._conn = MagicMock()
    db._conn.connect.return_value = MagicMock()  # ritorna un mock 'connection'
    db._conn.connect.return_value.cursor.return_value = MagicMock()
    # Inietta il lock come farebbe __init__
    db._lock = threading.Lock()

    n_threads = 8
    iterations = 50
    barrier = threading.Barrier(n_threads)

    def worker():
        barrier.wait()
        for _ in range(iterations):
            db.cursor()

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # connect() chiamato n_threads * iterations volte, ma serializzato
    assert db._conn.connect.call_count == n_threads * iterations
```

- [ ] **Step 2: Eseguire il test, deve fallire**

```bash
.venv\Scripts\python.exe -m pytest tests/test_db_lock.py -v
```
Expected: FAIL su `AttributeError: 'Database' object has no attribute '_lock'`.

- [ ] **Step 3: Modificare `fdp_app/db.py`**

Sostituire l'intero contenuto con:

```python
"""Wrapper attorno a db_connection.DatabaseConnection per dependency injection."""
from __future__ import annotations

import threading
from typing import Optional

from config_manager import ConfigManager
from db_connection import DatabaseConnection


class Database:
    """Wrapper iniettabile: in produzione delega a DatabaseConnection esistente.

    In test viene sostituito con MagicMock.

    Thread safety: pyodbc.Connection NON e' condivisibile fra thread.
    `cursor()` e' protetto da un Lock; questo serializza i thread di
    Waitress sul singolo `pyodbc.Connection` cached. Per il Piano 2 e'
    sufficiente (load basso). Piano 3 introdurra' una connessione per
    richiesta via `flask.g` per migliorare il throughput.
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None) -> None:
        self._cm = config_manager or ConfigManager()
        self._conn = DatabaseConnection(self._cm)
        self._lock = threading.Lock()

    def connect(self):
        return self._conn.connect()

    def disconnect(self) -> None:
        self._conn.disconnect()

    def cursor(self):
        """Ritorna un cursore. Caller responsabile della chiusura.

        Lock serializza l'accesso al `pyodbc.Connection` underlying.
        """
        with self._lock:
            return self.connect().cursor()
```

- [ ] **Step 4: Eseguire il test, deve passare**

```bash
.venv\Scripts\python.exe -m pytest tests/test_db_lock.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Eseguire tutta la suite**

```bash
.venv\Scripts\python.exe -m pytest -q
```
Expected: 35 passed.

- [ ] **Step 6: Commit**

```bash
git add fdp_app/db.py tests/test_db_lock.py
git commit -m "fix(db): serialize Database.cursor() with threading.Lock"
```

---

## Task 5: Script `set_workplace.py` per coordinate reali

**Files:**
- Create: `scripts/set_workplace.py`

- [ ] **Step 1: Creare lo script**

Creare `scripts/set_workplace.py`:

```python
"""Aggiorna interattivamente config/workplace.json con coordinate reali.

Eseguire dalla cartella principale del progetto:

    .venv\\Scripts\\python.exe scripts\\set_workplace.py

Lo script chiede nome, indirizzo, latitudine e longitudine del luogo
di lavoro e scrive il file in modo formattato.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKPLACE_JSON = ROOT / "config" / "workplace.json"


def _ask_float(prompt: str) -> float:
    while True:
        raw = input(prompt).strip()
        try:
            return float(raw)
        except ValueError:
            print(f"  '{raw}' non e' un numero valido. Riprovare.")


def main() -> int:
    print("=" * 60)
    print("Fogli di Percorso - Configurazione luogo di lavoro")
    print("=" * 60)
    print()
    print(f"Aggiornera': {WORKPLACE_JSON}")
    print()

    name = input("Nome sede [Sede aziendale]: ").strip() or "Sede aziendale"
    address = input("Indirizzo completo: ").strip()
    if not address:
        print("ERRORE: indirizzo obbligatorio.", file=sys.stderr)
        return 1

    print()
    print("Coordinate (puoi prenderle da Google Maps: click destro -> click sulle coordinate)")
    lat = _ask_float("Latitudine (es. 50.5234): ")
    lon = _ask_float("Longitudine (es. 3.2891): ")

    if not (-90 <= lat <= 90):
        print(f"ERRORE: latitudine {lat} fuori range [-90, 90].", file=sys.stderr)
        return 1
    if not (-180 <= lon <= 180):
        print(f"ERRORE: longitudine {lon} fuori range [-180, 180].", file=sys.stderr)
        return 1

    data = {"name": name, "address": address, "lat": lat, "lon": lon}

    WORKPLACE_JSON.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print()
    print(f"OK -> {WORKPLACE_JSON} aggiornato:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Verificare sintassi**

```bash
.venv\Scripts\python.exe -m py_compile scripts/set_workplace.py
```
Expected: nessun output (script valido).

- [ ] **Step 3: Eseguire la suite di test (nessun nuovo test, deve restare verde)**

```bash
.venv\Scripts\python.exe -m pytest -q
```
Expected: 35 passed.

- [ ] **Step 4: Commit**

```bash
git add scripts/set_workplace.py
git commit -m "chore: add interactive workplace coordinates setup script"
```

> **AZIONE OPERATIVA (fuori dai task):** quando l'utente avra' le coordinate reali della sede, eseguira' `python scripts/set_workplace.py` per aggiornare `config/workplace.json`. Questo commit modifica il file e va fatto separatamente (non da subagent).

---

# Fase B — Implementazione feature

## Task 6: Client OSRM/ORS — `routing.py`

**Files:**
- Create: `fdp_app/pathtracks/__init__.py` (empty)
- Create: `fdp_app/pathtracks/routing.py`
- Test: `tests/test_routing.py`

- [ ] **Step 1: Creare `fdp_app/pathtracks/__init__.py`** (file vuoto)

```python
```

- [ ] **Step 2: Scrivere `tests/test_routing.py`**

```python
"""Test del client di routing OSRM + fallback ORS."""
from __future__ import annotations

import pytest
import responses

from fdp_app.pathtracks.routing import (
    RoutingClient,
    RoutingError,
    OSRM_PATH,
)


OSRM_BASE = "https://router.project-osrm.org"
ORS_BASE = "https://api.openrouteservice.org"


@pytest.fixture
def mocked_responses():
    with responses.RequestsMock() as rsps:
        yield rsps


def test_osrm_returns_road_km_on_success(mocked_responses):
    mocked_responses.get(
        f"{OSRM_BASE}{OSRM_PATH}9.19,45.4642;9.20,45.50",
        json={
            "code": "Ok",
            "routes": [{"distance": 5300.5, "duration": 600}],
        },
        status=200,
    )
    client = RoutingClient(osrm_base=OSRM_BASE, ors_base=ORS_BASE, ors_api_key=None)

    km = client.road_km(start=(45.4642, 9.19), end=(45.50, 9.20))

    assert km == pytest.approx(5.3005, rel=1e-4)


def test_osrm_failure_without_ors_key_raises(mocked_responses):
    mocked_responses.get(
        f"{OSRM_BASE}{OSRM_PATH}9.19,45.4642;9.20,45.50",
        status=503,
    )
    client = RoutingClient(osrm_base=OSRM_BASE, ors_base=ORS_BASE, ors_api_key=None)

    with pytest.raises(RoutingError):
        client.road_km(start=(45.4642, 9.19), end=(45.50, 9.20))


def test_osrm_failure_with_ors_key_falls_back(mocked_responses):
    # OSRM fallisce
    mocked_responses.get(
        f"{OSRM_BASE}{OSRM_PATH}9.19,45.4642;9.20,45.50",
        status=503,
    )
    # ORS risponde
    mocked_responses.get(
        f"{ORS_BASE}/v2/directions/driving-car",
        json={
            "features": [{
                "properties": {"summary": {"distance": 4800.0, "duration": 540}}
            }]
        },
        status=200,
    )
    client = RoutingClient(osrm_base=OSRM_BASE, ors_base=ORS_BASE, ors_api_key="test-key")

    km = client.road_km(start=(45.4642, 9.19), end=(45.50, 9.20))

    assert km == pytest.approx(4.8, rel=1e-4)


def test_both_fail_raises_routing_error(mocked_responses):
    mocked_responses.get(
        f"{OSRM_BASE}{OSRM_PATH}9.19,45.4642;9.20,45.50",
        status=503,
    )
    mocked_responses.get(
        f"{ORS_BASE}/v2/directions/driving-car",
        status=500,
    )
    client = RoutingClient(osrm_base=OSRM_BASE, ors_base=ORS_BASE, ors_api_key="test-key")

    with pytest.raises(RoutingError):
        client.road_km(start=(45.4642, 9.19), end=(45.50, 9.20))


def test_cache_hit_does_not_call_http_twice(mocked_responses):
    mocked_responses.get(
        f"{OSRM_BASE}{OSRM_PATH}9.19,45.4642;9.20,45.50",
        json={"code": "Ok", "routes": [{"distance": 5300.5, "duration": 600}]},
        status=200,
    )
    client = RoutingClient(osrm_base=OSRM_BASE, ors_base=ORS_BASE, ors_api_key=None)

    km1 = client.road_km(start=(45.4642, 9.19), end=(45.50, 9.20))
    km2 = client.road_km(start=(45.4642, 9.19), end=(45.50, 9.20))

    assert km1 == km2
    assert len(mocked_responses.calls) == 1  # un solo HTTP, il secondo da cache


def test_invalid_osrm_json_raises_routing_error(mocked_responses):
    mocked_responses.get(
        f"{OSRM_BASE}{OSRM_PATH}9.19,45.4642;9.20,45.50",
        json={"code": "NoRoute", "message": "Impossible route"},
        status=200,
    )
    client = RoutingClient(osrm_base=OSRM_BASE, ors_base=ORS_BASE, ors_api_key=None)

    with pytest.raises(RoutingError):
        client.road_km(start=(45.4642, 9.19), end=(45.50, 9.20))
```

- [ ] **Step 3: Eseguire i test, devono fallire**

```bash
.venv\Scripts\python.exe -m pytest tests/test_routing.py -v
```
Expected: `ModuleNotFoundError: No module named 'fdp_app.pathtracks.routing'`.

- [ ] **Step 4: Creare `fdp_app/pathtracks/routing.py`**

```python
"""Client per il calcolo della distanza stradale (OSRM primario, ORS fallback).

Usa OSRM pubblico se disponibile; in caso di errore, prova ORS se la
API key e' configurata. Cache in-process per coppia (lat,lon) -> km.

Note di formato:
- OSRM: coordinate in ordine lon,lat nell'URL; distance in metri.
- ORS: coordinate sempre lon,lat; distance in metri.
- Nominatim: lat e lon come query string separati.

Nota cache: l'utente puo' avere un solo punto di partenza attivo, quindi
la cache contiene tipicamente 1-2 entry per processo. Non serve eviction.
"""
from __future__ import annotations

from threading import Lock
from typing import Optional, Tuple

import requests

OSRM_PATH = "/route/v1/driving/"
ORS_PATH = "/v2/directions/driving-car"

LatLon = Tuple[float, float]


class RoutingError(Exception):
    """Raised quando nessun provider riesce a calcolare la rotta."""


class RoutingClient:
    def __init__(
        self,
        osrm_base: str,
        ors_base: str,
        ors_api_key: Optional[str],
        timeout_s: float = 6.0,
    ) -> None:
        self._osrm_base = osrm_base.rstrip("/")
        self._ors_base = ors_base.rstrip("/")
        self._ors_api_key = ors_api_key
        self._timeout = timeout_s
        self._cache: dict[Tuple[LatLon, LatLon], float] = {}
        self._lock = Lock()

    def road_km(self, *, start: LatLon, end: LatLon) -> float:
        """Ritorna distanza stradale in km. Tenta OSRM, poi ORS.

        Raises RoutingError se nessuno dei due risponde correttamente.
        """
        key = (start, end)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                return cached

        km = self._try_osrm(start, end)
        if km is None:
            km = self._try_ors(start, end)
        if km is None:
            raise RoutingError(
                f"Nessun provider ha calcolato la rotta {start} -> {end}"
            )

        with self._lock:
            self._cache[key] = km
        return km

    def _try_osrm(self, start: LatLon, end: LatLon) -> Optional[float]:
        # OSRM richiede lon,lat nell'URL
        url = (
            f"{self._osrm_base}{OSRM_PATH}"
            f"{start[1]},{start[0]};{end[1]},{end[0]}"
        )
        try:
            resp = requests.get(url, params={"overview": "false"}, timeout=self._timeout)
        except requests.RequestException:
            return None
        if resp.status_code != 200:
            return None
        try:
            data = resp.json()
        except ValueError:
            return None
        if data.get("code") != "Ok":
            return None
        routes = data.get("routes") or []
        if not routes:
            return None
        meters = routes[0].get("distance")
        if not isinstance(meters, (int, float)):
            return None
        return float(meters) / 1000.0

    def _try_ors(self, start: LatLon, end: LatLon) -> Optional[float]:
        if not self._ors_api_key:
            return None
        url = f"{self._ors_base}{ORS_PATH}"
        params = {
            "api_key": self._ors_api_key,
            "start": f"{start[1]},{start[0]}",
            "end": f"{end[1]},{end[0]}",
        }
        try:
            resp = requests.get(url, params=params, timeout=self._timeout)
        except requests.RequestException:
            return None
        if resp.status_code != 200:
            return None
        try:
            data = resp.json()
        except ValueError:
            return None
        features = data.get("features") or []
        if not features:
            return None
        summary = features[0].get("properties", {}).get("summary", {})
        meters = summary.get("distance")
        if not isinstance(meters, (int, float)):
            return None
        return float(meters) / 1000.0
```

- [ ] **Step 5: Eseguire i test, devono passare**

```bash
.venv\Scripts\python.exe -m pytest tests/test_routing.py -v
```
Expected: 6 passed.

- [ ] **Step 6: Eseguire tutta la suite**

```bash
.venv\Scripts\python.exe -m pytest -q
```
Expected: 41 passed (35 + 6 nuovi).

- [ ] **Step 7: Commit**

```bash
git add fdp_app/pathtracks/__init__.py fdp_app/pathtracks/routing.py tests/test_routing.py
git commit -m "feat(routing): OSRM client with ORS fallback and in-process cache"
```

---

## Task 7: `CoordinateRepo` — CRUD su `PathTrackCoordinates` con `geography`

**Files:**
- Create: `fdp_app/repos/coordinate_repo.py`
- Test: `tests/test_coordinate_repo.py`

- [ ] **Step 1: Scrivere `tests/test_coordinate_repo.py`**

```python
"""Test del repository CoordinateRepo (mock cursor SQL Server)."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from fdp_app.repos.coordinate_repo import (
    CoordinateRepo,
    ActiveCoordinate,
)


def _make_db(fetchone_row=None):
    db = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone_row
    db.cursor.return_value = cursor
    return db, cursor


def test_find_active_returns_none_when_no_row():
    db, cursor = _make_db(fetchone_row=None)
    repo = CoordinateRepo(db)

    result = repo.find_active(employee_hire_history_id=42)

    assert result is None
    cursor.close.assert_called_once()


def test_find_active_returns_coordinate_when_row_exists():
    row = (
        100,                       # PathTrackCoordinateId
        "Casa Mario",              # PathTrackName
        45.4642,                   # lat (from Coordinates.Lat)
        9.1900,                    # lon (from Coordinates.Long)
        12.345,                    # RoadKmToWorkplace
    )
    db, cursor = _make_db(fetchone_row=row)
    repo = CoordinateRepo(db)

    result = repo.find_active(employee_hire_history_id=42)

    assert isinstance(result, ActiveCoordinate)
    assert result.coordinate_id == 100
    assert result.label == "Casa Mario"
    assert result.lat == 45.4642
    assert result.lon == 9.1900
    assert result.road_km_to_workplace == pytest.approx(12.345)


def test_find_active_query_filters_by_employee_and_dateout_null():
    db, cursor = _make_db(fetchone_row=None)
    repo = CoordinateRepo(db)

    repo.find_active(employee_hire_history_id=42)

    sql_text, *params = cursor.execute.call_args[0]
    assert "EmployeerHireHistoryId = ?" in sql_text
    assert "DateOut IS NULL" in sql_text
    assert params == [42]


def test_insert_creates_geography_point_with_road_km():
    db, cursor = _make_db()
    cursor.fetchone.return_value = (200,)  # new PathTrackCoordinateId via OUTPUT INSERTED
    repo = CoordinateRepo(db)

    new_id = repo.insert(
        employee_hire_history_id=42,
        label="Casa Mario",
        lat=45.4642,
        lon=9.1900,
        road_km_to_workplace=12.345,
    )

    assert new_id == 200
    sql_text, *params = cursor.execute.call_args[0]
    assert "INSERT INTO Employee.fdp.PathTrackCoordinates" in sql_text
    assert "geography::Point(?, ?, 4326)" in sql_text
    # Params: emp_id, label, lat, lon, road_km
    assert params == [42, "Casa Mario", 45.4642, 9.1900, 12.345]
    cursor.close.assert_called_once()


def test_soft_delete_sets_dateout_for_active_record():
    db, cursor = _make_db()
    cursor.rowcount = 1
    repo = CoordinateRepo(db)

    deleted = repo.soft_delete(coordinate_id=100, employee_hire_history_id=42)

    assert deleted is True
    sql_text, *params = cursor.execute.call_args[0]
    assert "UPDATE Employee.fdp.PathTrackCoordinates" in sql_text
    assert "SET DateOut = GETDATE()" in sql_text
    assert "PathTrackCoordinateId = ?" in sql_text
    assert "EmployeerHireHistoryId = ?" in sql_text
    assert "DateOut IS NULL" in sql_text
    assert params == [100, 42]


def test_soft_delete_returns_false_when_nothing_updated():
    db, cursor = _make_db()
    cursor.rowcount = 0
    repo = CoordinateRepo(db)

    deleted = repo.soft_delete(coordinate_id=999, employee_hire_history_id=42)

    assert deleted is False


def test_insert_closes_cursor_on_exception():
    db, cursor = _make_db()
    cursor.execute.side_effect = RuntimeError("DB down")
    repo = CoordinateRepo(db)

    with pytest.raises(RuntimeError):
        repo.insert(
            employee_hire_history_id=42,
            label="x",
            lat=1.0,
            lon=2.0,
            road_km_to_workplace=3.0,
        )
    cursor.close.assert_called_once()
```

- [ ] **Step 2: Eseguire i test, devono fallire**

```bash
.venv\Scripts\python.exe -m pytest tests/test_coordinate_repo.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Creare `fdp_app/repos/coordinate_repo.py`**

```python
"""Repository per fdp.PathTrackCoordinates (gestione punto di partenza)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


_QUERY_FIND_ACTIVE = """
SELECT TOP 1
    PathTrackCoordinateId,
    PathTrackName,
    Coordinates.Lat AS lat,
    Coordinates.Long AS lon,
    RoadKmToWorkplace
FROM Employee.fdp.PathTrackCoordinates
WHERE EmployeerHireHistoryId = ?
  AND DateOut IS NULL
ORDER BY DateSys DESC
"""

_QUERY_INSERT = """
INSERT INTO Employee.fdp.PathTrackCoordinates
    (EmployeerHireHistoryId, PathTrackName, Coordinates, RoadKmToWorkplace,
     DateOut, DateSys)
OUTPUT INSERTED.PathTrackCoordinateId
VALUES
    (?, ?, geography::Point(?, ?, 4326), ?, NULL, GETDATE())
"""

_QUERY_SOFT_DELETE = """
UPDATE Employee.fdp.PathTrackCoordinates
SET DateOut = GETDATE()
WHERE PathTrackCoordinateId = ?
  AND EmployeerHireHistoryId = ?
  AND DateOut IS NULL
"""


@dataclass(frozen=True)
class ActiveCoordinate:
    coordinate_id: int
    label: str
    lat: float
    lon: float
    road_km_to_workplace: Optional[float]


class CoordinateRepo:
    def __init__(self, db) -> None:
        self._db = db

    def find_active(self, employee_hire_history_id: int) -> Optional[ActiveCoordinate]:
        cursor = self._db.cursor()
        try:
            cursor.execute(_QUERY_FIND_ACTIVE, employee_hire_history_id)
            row = cursor.fetchone()
        finally:
            cursor.close()
        if row is None:
            return None
        return ActiveCoordinate(
            coordinate_id=row[0],
            label=row[1],
            lat=float(row[2]),
            lon=float(row[3]),
            road_km_to_workplace=float(row[4]) if row[4] is not None else None,
        )

    def insert(
        self,
        *,
        employee_hire_history_id: int,
        label: str,
        lat: float,
        lon: float,
        road_km_to_workplace: float,
    ) -> int:
        cursor = self._db.cursor()
        try:
            cursor.execute(
                _QUERY_INSERT,
                employee_hire_history_id,
                label,
                lat,
                lon,
                road_km_to_workplace,
            )
            row = cursor.fetchone()
            return int(row[0])
        finally:
            cursor.close()

    def soft_delete(
        self, *, coordinate_id: int, employee_hire_history_id: int
    ) -> bool:
        cursor = self._db.cursor()
        try:
            cursor.execute(_QUERY_SOFT_DELETE, coordinate_id, employee_hire_history_id)
            return cursor.rowcount > 0
        finally:
            cursor.close()
```

- [ ] **Step 4: Eseguire i test, devono passare**

```bash
.venv\Scripts\python.exe -m pytest tests/test_coordinate_repo.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Eseguire tutta la suite**

```bash
.venv\Scripts\python.exe -m pytest -q
```
Expected: 48 passed (41 + 7 nuovi).

- [ ] **Step 6: Commit**

```bash
git add fdp_app/repos/coordinate_repo.py tests/test_coordinate_repo.py
git commit -m "feat(repos): CoordinateRepo with geography::Point CRUD and soft-delete"
```

---

## Task 8: `CoordinateService` — orchestrazione

**Files:**
- Create: `fdp_app/coordinates/__init__.py` (empty)
- Create: `fdp_app/coordinates/service.py`
- Test: `tests/test_coordinates_service.py`

- [ ] **Step 1: Creare `fdp_app/coordinates/__init__.py`** (file vuoto)

```python
```

- [ ] **Step 2: Scrivere `tests/test_coordinates_service.py`**

```python
"""Test del CoordinateService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from fdp_app.coordinates.service import (
    CoordinateService,
    ActiveCoordinateAlreadyExists,
)
from fdp_app.pathtracks.routing import RoutingError
from fdp_app.repos.coordinate_repo import ActiveCoordinate


def _service(repo=None, routing=None, workplace=None):
    repo = repo or MagicMock()
    routing = routing or MagicMock()
    workplace = workplace or {"lat": 50.0, "lon": 3.0}
    return CoordinateService(repo=repo, routing=routing, workplace=workplace), repo, routing


def test_find_active_delegates_to_repo():
    expected = ActiveCoordinate(1, "x", 45.0, 9.0, 12.5)
    svc, repo, _ = _service()
    repo.find_active.return_value = expected

    result = svc.find_active(employee_hire_history_id=42)

    assert result is expected
    repo.find_active.assert_called_once_with(42)


def test_create_when_no_active_calls_routing_and_inserts():
    svc, repo, routing = _service(workplace={"lat": 50.5, "lon": 3.3})
    repo.find_active.return_value = None
    routing.road_km.return_value = 12.345
    repo.insert.return_value = 200

    new_id = svc.create(
        employee_hire_history_id=42, label="Casa", lat=45.0, lon=9.0
    )

    assert new_id == 200
    routing.road_km.assert_called_once_with(
        start=(45.0, 9.0), end=(50.5, 3.3)
    )
    repo.insert.assert_called_once_with(
        employee_hire_history_id=42,
        label="Casa",
        lat=45.0,
        lon=9.0,
        road_km_to_workplace=12.345,
    )


def test_create_when_active_exists_raises():
    svc, repo, _ = _service()
    repo.find_active.return_value = ActiveCoordinate(1, "old", 1, 2, 3)

    with pytest.raises(ActiveCoordinateAlreadyExists):
        svc.create(employee_hire_history_id=42, label="x", lat=1.0, lon=2.0)

    repo.insert.assert_not_called()


def test_create_propagates_routing_error():
    svc, repo, routing = _service()
    repo.find_active.return_value = None
    routing.road_km.side_effect = RoutingError("OSRM down")

    with pytest.raises(RoutingError):
        svc.create(employee_hire_history_id=42, label="x", lat=1.0, lon=2.0)

    repo.insert.assert_not_called()


def test_delete_delegates_to_repo():
    svc, repo, _ = _service()
    repo.soft_delete.return_value = True

    result = svc.delete(coordinate_id=100, employee_hire_history_id=42)

    assert result is True
    repo.soft_delete.assert_called_once_with(
        coordinate_id=100, employee_hire_history_id=42
    )
```

- [ ] **Step 3: Eseguire i test, devono fallire**

```bash
.venv\Scripts\python.exe -m pytest tests/test_coordinates_service.py -v
```
Expected: ModuleNotFoundError.

- [ ] **Step 4: Creare `fdp_app/coordinates/service.py`**

```python
"""Logica di business per la gestione del punto di partenza."""
from __future__ import annotations

from typing import Optional

from fdp_app.pathtracks.routing import RoutingClient
from fdp_app.repos.coordinate_repo import ActiveCoordinate, CoordinateRepo


class ActiveCoordinateAlreadyExists(Exception):
    """Raised quando si tenta di inserire un punto mentre ne esiste gia'
    uno attivo (DateOut IS NULL) per lo stesso dipendente."""


class CoordinateService:
    """Orchestrazione: routing + repo. Single-responsibility per gestione punto."""

    def __init__(
        self,
        repo: CoordinateRepo,
        routing: RoutingClient,
        workplace: dict,
    ) -> None:
        self._repo = repo
        self._routing = routing
        self._workplace = workplace

    def find_active(self, employee_hire_history_id: int) -> Optional[ActiveCoordinate]:
        return self._repo.find_active(employee_hire_history_id)

    def create(
        self,
        *,
        employee_hire_history_id: int,
        label: str,
        lat: float,
        lon: float,
    ) -> int:
        existing = self._repo.find_active(employee_hire_history_id)
        if existing is not None:
            raise ActiveCoordinateAlreadyExists(
                f"Il dipendente {employee_hire_history_id} ha gia' un punto attivo "
                f"(id={existing.coordinate_id}). Cancellarlo prima di crearne uno nuovo."
            )

        road_km = self._routing.road_km(
            start=(lat, lon),
            end=(self._workplace["lat"], self._workplace["lon"]),
        )
        return self._repo.insert(
            employee_hire_history_id=employee_hire_history_id,
            label=label,
            lat=lat,
            lon=lon,
            road_km_to_workplace=road_km,
        )

    def delete(
        self, *, coordinate_id: int, employee_hire_history_id: int
    ) -> bool:
        return self._repo.soft_delete(
            coordinate_id=coordinate_id,
            employee_hire_history_id=employee_hire_history_id,
        )
```

- [ ] **Step 5: Eseguire i test, devono passare**

```bash
.venv\Scripts\python.exe -m pytest tests/test_coordinates_service.py -v
```
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add fdp_app/coordinates/__init__.py fdp_app/coordinates/service.py tests/test_coordinates_service.py
git commit -m "feat(coordinates): service with routing + repo orchestration"
```

---

## Task 9: Route `/coordinates` GET (visualizzazione mappa)

**Files:**
- Create: `fdp_app/coordinates/routes.py`
- Create: `fdp_app/templates/coordinates/index.html`
- Modify: `fdp_app/__init__.py` (registrare il blueprint)
- Test: `tests/test_coordinates_routes.py`

- [ ] **Step 1: Scrivere `tests/test_coordinates_routes.py` (solo per la GET)**

```python
"""Test E2E della route /coordinates."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fdp_app.repos.coordinate_repo import ActiveCoordinate


@pytest.fixture
def mock_coord_repo():
    with patch("fdp_app.coordinates.routes.CoordinateRepo") as repo_cls:
        instance = MagicMock()
        repo_cls.return_value = instance
        yield instance


@pytest.fixture
def mock_routing():
    with patch("fdp_app.coordinates.routes.RoutingClient") as cls:
        instance = MagicMock()
        cls.return_value = instance
        yield instance


def _login(client, employee_hire_history_id=10):
    with client.session_transaction() as sess:
        sess["user_id"] = employee_hire_history_id
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = 5
        sess["function_code"] = 70


def test_get_coordinates_requires_login(client):
    response = client.get("/coordinates", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_get_coordinates_shows_no_active_point(client, mock_coord_repo, mock_routing):
    _login(client)
    mock_coord_repo.find_active.return_value = None

    response = client.get("/coordinates")

    assert response.status_code == 200
    assert b"Nessun punto attivo" in response.data
    assert b"id=\"map\"" in response.data  # contenitore mappa


def test_get_coordinates_shows_active_point(client, mock_coord_repo, mock_routing):
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(
        coordinate_id=100,
        label="Casa Mario",
        lat=45.4642,
        lon=9.19,
        road_km_to_workplace=12.345,
    )

    response = client.get("/coordinates")

    assert response.status_code == 200
    assert b"Casa Mario" in response.data
    assert b"45.4642" in response.data
    assert b"9.19" in response.data
    assert b"12.345" in response.data or b"12,345" in response.data
```

- [ ] **Step 2: Eseguire i test, devono fallire**

```bash
.venv\Scripts\python.exe -m pytest tests/test_coordinates_routes.py -v
```
Expected: failures (route non esiste).

- [ ] **Step 3: Creare `fdp_app/coordinates/routes.py`** (GET + scaffolding POST per ora vuoti)

```python
"""Route per la gestione del punto di partenza."""
from __future__ import annotations

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request,
    session, url_for,
)

from fdp_app.auth.decorators import login_required
from fdp_app.coordinates.service import (
    ActiveCoordinateAlreadyExists,
    CoordinateService,
)
from fdp_app.pathtracks.routing import RoutingClient, RoutingError
from fdp_app.repos.coordinate_repo import CoordinateRepo

bp = Blueprint("coordinates", __name__)


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


@bp.route("/coordinates", methods=["GET"])
@login_required
def index():
    service = _build_service()
    active = service.find_active(session["user_id"])
    workplace = current_app.config["_settings_cls"].workplace()
    return render_template(
        "coordinates/index.html",
        active=active,
        workplace=workplace,
    )
```

- [ ] **Step 4: Creare `fdp_app/templates/coordinates/index.html`**

```html
{% extends "base.html" %}
{% block title %}Punto di partenza - Fogli di Percorso{% endblock %}
{% block head_extra %}
<link rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css">
{% endblock %}
{% block content %}
<h2>Punto di partenza</h2>

{% if active %}
<div class="card mb-3">
    <div class="card-body">
        <h5 class="card-title">{{ active.label }}</h5>
        <p class="card-text mb-1">
            Coordinate: <code>{{ active.lat }}, {{ active.lon }}</code>
        </p>
        {% if active.road_km_to_workplace is not none %}
        <p class="card-text mb-1">
            Distanza stradale verso la sede:
            <strong>{{ "%.3f"|format(active.road_km_to_workplace) }} km</strong>
        </p>
        {% endif %}
        <form action="{{ url_for('coordinates.delete') }}" method="post" class="mt-2">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <input type="hidden" name="coordinate_id" value="{{ active.coordinate_id }}">
            <button type="submit" class="btn btn-outline-danger btn-sm"
                    onclick="return confirm('Cancellare il punto di partenza?');">
                Cancella punto
            </button>
        </form>
    </div>
</div>
{% else %}
<div class="alert alert-info">
    Nessun punto attivo. Clicca sulla mappa per scegliere il tuo punto di partenza.
</div>
{% endif %}

<div id="map" class="map-container mb-3"></div>

{% if not active %}
<form id="save-form" action="{{ url_for('coordinates.create') }}" method="post"
      class="card card-body" style="display:none;">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <input type="hidden" name="lat" id="input-lat">
    <input type="hidden" name="lon" id="input-lon">
    <div class="mb-2">
        <label class="form-label" for="input-label">Etichetta (es. "Casa", "Via Roma 5")</label>
        <input class="form-control" type="text" name="label" id="input-label"
               required maxlength="200" autocomplete="off">
    </div>
    <p class="text-muted">
        Coordinate selezionate: <code id="display-coords">-</code><br>
        Indirizzo (auto): <code id="display-address">-</code>
    </p>
    <button type="submit" class="btn btn-primary">Salva punto di partenza</button>
</form>
{% endif %}

<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
window.FDP_WORKPLACE = {{ {"lat": workplace.lat, "lon": workplace.lon, "name": workplace.name}|tojson }};
{% if active %}
window.FDP_ACTIVE = {{ {"lat": active.lat, "lon": active.lon, "label": active.label}|tojson }};
{% else %}
window.FDP_ACTIVE = null;
{% endif %}
</script>
<script src="{{ url_for('static', filename='js/coordinates.js') }}"></script>
{% endblock %}
```

- [ ] **Step 5: Creare `fdp_app/static/js/coordinates.js`** (minimo per ora — solo mappa)

```javascript
(function () {
    "use strict";

    var wp = window.FDP_WORKPLACE;
    var active = window.FDP_ACTIVE;

    var center = active ? [active.lat, active.lon] : [wp.lat, wp.lon];
    var map = L.map("map").setView(center, 9);

    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap"
    }).addTo(map);

    // Marker sede aziendale (sempre presente)
    L.marker([wp.lat, wp.lon], {title: wp.name})
        .bindPopup("<b>" + wp.name + "</b>")
        .addTo(map);

    if (active) {
        L.marker([active.lat, active.lon], {title: active.label})
            .bindPopup("<b>" + active.label + "</b>")
            .addTo(map);
    } else {
        // Click handler per scegliere un punto
        var pickedMarker = null;
        map.on("click", function (e) {
            var lat = e.latlng.lat;
            var lon = e.latlng.lng;

            if (pickedMarker) {
                map.removeLayer(pickedMarker);
            }
            pickedMarker = L.marker([lat, lon]).addTo(map);

            document.getElementById("input-lat").value = lat.toFixed(6);
            document.getElementById("input-lon").value = lon.toFixed(6);
            document.getElementById("display-coords").textContent =
                lat.toFixed(6) + ", " + lon.toFixed(6);
            document.getElementById("display-address").textContent = "(caricamento...)";
            document.getElementById("save-form").style.display = "block";

            // Reverse geocoding via Nominatim (lato browser, no proxy server)
            var url = "https://nominatim.openstreetmap.org/reverse?format=json&lat="
                + lat + "&lon=" + lon + "&zoom=18&addressdetails=1";
            fetch(url, {headers: {"Accept": "application/json"}})
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    var addr = (data && data.display_name) || "(indirizzo non trovato)";
                    document.getElementById("display-address").textContent = addr;
                    var labelInput = document.getElementById("input-label");
                    if (!labelInput.value) {
                        labelInput.value = addr.substring(0, 200);
                    }
                })
                .catch(function () {
                    document.getElementById("display-address").textContent = "(errore reverse-geocoding)";
                });
        });
    }
}());
```

- [ ] **Step 6: Modificare `fdp_app/__init__.py` per registrare il blueprint**

Nella funzione `_register_blueprints`, aggiungere:

```python
    from fdp_app.coordinates.routes import bp as coordinates_bp
    app.register_blueprint(coordinates_bp)
```

L'ordine consigliato dopo `dashboard_bp`.

- [ ] **Step 7: Eseguire i test GET**

```bash
.venv\Scripts\python.exe -m pytest tests/test_coordinates_routes.py -v -k "test_get_"
```
Expected: 3 passed.

- [ ] **Step 8: Eseguire tutta la suite**

```bash
.venv\Scripts\python.exe -m pytest -q
```
Expected: 56 passed (48 + 3 GET + 5 service-test = 56 totali; in realta' 53 + 3 = 56).

> Conteggio aggiornato: 48 (dopo Task 7) + 5 (Task 8 service) = 53. Aggiungere i 3 di questo task = 56. Se il conteggio differisce di poco va bene; quel che conta e' "tutti verdi".

- [ ] **Step 9: Commit**

```bash
git add fdp_app/coordinates/routes.py fdp_app/templates/coordinates/ fdp_app/static/js/coordinates.js fdp_app/__init__.py tests/test_coordinates_routes.py
git commit -m "feat(coordinates): GET /coordinates with Leaflet map and reverse geocoding"
```

---

## Task 10: Route `/coordinates` POST create + delete

**Files:**
- Modify: `fdp_app/coordinates/routes.py`
- Modify: `tests/test_coordinates_routes.py` (aggiungere tests POST)

- [ ] **Step 1: Aggiungere test POST a `tests/test_coordinates_routes.py`**

Aggiungere al file esistente:

```python
def test_post_create_inserts_when_no_active(client, mock_coord_repo, mock_routing):
    _login(client)
    mock_coord_repo.find_active.return_value = None
    mock_routing.road_km.return_value = 12.345
    mock_coord_repo.insert.return_value = 200

    response = client.post(
        "/coordinates",
        data={"lat": "45.4642", "lon": "9.19", "label": "Casa"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/coordinates" in response.headers["Location"]
    mock_coord_repo.insert.assert_called_once()
    kwargs = mock_coord_repo.insert.call_args.kwargs
    assert kwargs["employee_hire_history_id"] == 10
    assert kwargs["label"] == "Casa"
    assert kwargs["lat"] == 45.4642
    assert kwargs["lon"] == 9.19
    assert kwargs["road_km_to_workplace"] == 12.345


def test_post_create_rejects_when_active_exists(client, mock_coord_repo, mock_routing):
    from fdp_app.repos.coordinate_repo import ActiveCoordinate
    _login(client)
    mock_coord_repo.find_active.return_value = ActiveCoordinate(1, "x", 1.0, 2.0, 3.0)

    response = client.post(
        "/coordinates",
        data={"lat": "45.0", "lon": "9.0", "label": "y"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"esiste gi" in response.data.lower() or b"cancellare" in response.data.lower()
    mock_coord_repo.insert.assert_not_called()


def test_post_create_handles_routing_error(client, mock_coord_repo, mock_routing):
    from fdp_app.pathtracks.routing import RoutingError
    _login(client)
    mock_coord_repo.find_active.return_value = None
    mock_routing.road_km.side_effect = RoutingError("OSRM down")

    response = client.post(
        "/coordinates",
        data={"lat": "45.0", "lon": "9.0", "label": "y"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"mappe" in response.data.lower() or b"riprov" in response.data.lower()
    mock_coord_repo.insert.assert_not_called()


def test_post_create_validates_lat_lon_range(client, mock_coord_repo, mock_routing):
    _login(client)

    response = client.post(
        "/coordinates",
        data={"lat": "200", "lon": "9.0", "label": "y"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"non valid" in response.data.lower()
    mock_coord_repo.insert.assert_not_called()


def test_post_delete_soft_deletes_owned(client, mock_coord_repo):
    _login(client)
    mock_coord_repo.soft_delete.return_value = True

    response = client.post(
        "/coordinates/delete",
        data={"coordinate_id": "100"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/coordinates" in response.headers["Location"]
    mock_coord_repo.soft_delete.assert_called_once_with(
        coordinate_id=100, employee_hire_history_id=10
    )


def test_post_delete_not_owned_returns_404(client, mock_coord_repo):
    _login(client)
    mock_coord_repo.soft_delete.return_value = False  # nessuna riga aggiornata

    response = client.post(
        "/coordinates/delete",
        data={"coordinate_id": "999"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"non trovato" in response.data.lower() or b"non posseduto" in response.data.lower()
```

- [ ] **Step 2: Eseguire i test, devono fallire**

```bash
.venv\Scripts\python.exe -m pytest tests/test_coordinates_routes.py -v -k "test_post"
```
Expected: failures (POST routes non implementate).

- [ ] **Step 3: Estendere `fdp_app/coordinates/routes.py`**

Aggiungere queste due route al modulo (dopo `index`):

```python
@bp.route("/coordinates", methods=["POST"])
@login_required
def create():
    try:
        lat = float(request.form.get("lat") or "")
        lon = float(request.form.get("lon") or "")
    except ValueError:
        flash("Coordinate non valide.", "danger")
        return redirect(url_for("coordinates.index"))

    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        flash("Coordinate non valide (lat/lon fuori range).", "danger")
        return redirect(url_for("coordinates.index"))

    label = (request.form.get("label") or "").strip()
    if not label:
        flash("Etichetta obbligatoria.", "danger")
        return redirect(url_for("coordinates.index"))
    if len(label) > 200:
        label = label[:200]

    service = _build_service()
    try:
        service.create(
            employee_hire_history_id=session["user_id"],
            label=label,
            lat=lat,
            lon=lon,
        )
        flash("Punto di partenza salvato.", "success")
    except ActiveCoordinateAlreadyExists:
        flash(
            "Esiste gia' un punto attivo. Cancellarlo prima di crearne uno nuovo.",
            "danger",
        )
    except RoutingError:
        flash(
            "Servizio mappe temporaneamente non disponibile. Riprovare piu' tardi.",
            "danger",
        )

    return redirect(url_for("coordinates.index"))


@bp.route("/coordinates/delete", methods=["POST"])
@login_required
def delete():
    try:
        coordinate_id = int(request.form.get("coordinate_id") or "")
    except ValueError:
        flash("Identificativo punto non valido.", "danger")
        return redirect(url_for("coordinates.index"))

    service = _build_service()
    ok = service.delete(
        coordinate_id=coordinate_id,
        employee_hire_history_id=session["user_id"],
    )
    if ok:
        flash("Punto di partenza cancellato.", "success")
    else:
        flash("Punto non trovato o non posseduto.", "warning")
    return redirect(url_for("coordinates.index"))
```

- [ ] **Step 4: Eseguire i test, devono passare**

```bash
.venv\Scripts\python.exe -m pytest tests/test_coordinates_routes.py -v
```
Expected: 9 passed (3 GET + 6 POST).

- [ ] **Step 5: Eseguire tutta la suite**

```bash
.venv\Scripts\python.exe -m pytest -q
```
Expected: 62 passed (56 + 6 POST).

- [ ] **Step 6: Commit**

```bash
git add fdp_app/coordinates/routes.py tests/test_coordinates_routes.py
git commit -m "feat(coordinates): POST create/delete with validation and CSRF"
```

---

## Task 11: Link dashboard → /coordinates

**Files:**
- Modify: `fdp_app/templates/dashboard/index.html`

- [ ] **Step 1: Modificare `fdp_app/templates/dashboard/index.html`**

Trovare il bottone:

```html
<a class="btn btn-outline-primary disabled" href="#">Disponibile nel Piano 2</a>
```

(quello dentro la card "Punto di partenza")

Sostituire con:

```html
<a class="btn btn-outline-primary" href="{{ url_for('coordinates.index') }}">Vai alla mappa</a>
```

(rimuovere la classe `disabled` e usare `url_for`)

- [ ] **Step 2: Aggiungere il test in `tests/test_dashboard.py`**

Aggiungere al file esistente:

```python
def test_dashboard_card_links_to_coordinates(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 10
        sess["full_name"] = "Rossi Mario"
        sess["sub_cdc_id"] = 7
        sess["function_code"] = 65

    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"/coordinates" in response.data
    # La card "Punto di partenza" non e' piu' disabled
    assert b"Disponibile nel Piano 2" not in response.data
```

- [ ] **Step 3: Eseguire i test**

```bash
.venv\Scripts\python.exe -m pytest tests/test_dashboard.py -v
```
Expected: 4 passed (3 originali + 1 nuovo).

- [ ] **Step 4: Commit**

```bash
git add fdp_app/templates/dashboard/index.html tests/test_dashboard.py
git commit -m "feat(dashboard): activate Punto di partenza card with link to /coordinates"
```

---

## Task 12: Aggiornare conftest per rate-limiter reset cross-test

**Files:**
- Modify: `tests/conftest.py`

> **Motivazione:** il singleton `_rate_limiter` in `fdp_app/auth/routes` puo' inquinare i test futuri (Piano 3+). Conviene resettarlo a livello globale, non solo nei test auth.

- [ ] **Step 1: Aggiungere fixture autouse in `tests/conftest.py`**

Sotto la fixture `client`, aggiungere:

```python
@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset del singleton rate_limiter tra ogni test per evitare inquinamento."""
    import fdp_app.auth.routes as auth_routes
    auth_routes._rate_limiter = None
    yield
    auth_routes._rate_limiter = None
```

- [ ] **Step 2: Rimuovere la fixture omonima in `tests/test_auth_routes.py`** (ora duplicata)

Cercare e RIMUOVERE (se esiste):

```python
@pytest.fixture(autouse=True)
def reset_rate_limiter():
    import fdp_app.auth.routes as routes
    routes._rate_limiter = None
    yield
    routes._rate_limiter = None
```

(L'autouse globale del conftest la copre.)

- [ ] **Step 3: Eseguire tutta la suite**

```bash
.venv\Scripts\python.exe -m pytest -q
```
Expected: 63 passed (tutto verde, conteggio invariato salvo i 4 dashboard del Task 11).

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_auth_routes.py
git commit -m "test: move rate-limiter reset fixture to conftest (global autouse)"
```

---

## Task 13: Logging del flusso coordinate

**Files:**
- Modify: `fdp_app/coordinates/routes.py`

- [ ] **Step 1: Aggiungere `current_app.logger.info(...)` agli eventi chiave**

Modificare le route in `fdp_app/coordinates/routes.py`:

Nella `create()`, dopo `service.create(...)` riuscita, aggiungere:

```python
        current_app.logger.info(
            "Coordinate created: user_id=%s coord_id=set", session["user_id"]
        )
```

Wait — il service ritorna il new_id. Modifichiamo:

DA:
```python
        service.create(
            employee_hire_history_id=session["user_id"],
            label=label,
            lat=lat,
            lon=lon,
        )
        flash("Punto di partenza salvato.", "success")
```

A:
```python
        new_id = service.create(
            employee_hire_history_id=session["user_id"],
            label=label,
            lat=lat,
            lon=lon,
        )
        current_app.logger.info(
            "Coordinate created: user_id=%s coord_id=%s",
            session["user_id"], new_id,
        )
        flash("Punto di partenza salvato.", "success")
```

Nella `delete()`, dopo `service.delete(...)`:

DA:
```python
    if ok:
        flash("Punto di partenza cancellato.", "success")
```

A:
```python
    if ok:
        current_app.logger.info(
            "Coordinate deleted: user_id=%s coord_id=%s",
            session["user_id"], coordinate_id,
        )
        flash("Punto di partenza cancellato.", "success")
```

Nella `create()`, nei rami di errore, aggiungere logging al livello appropriato:

DA:
```python
    except RoutingError:
        flash(
            "Servizio mappe temporaneamente non disponibile. Riprovare piu' tardi.",
            "danger",
        )
```

A:
```python
    except RoutingError as e:
        current_app.logger.warning(
            "Routing failure for user_id=%s: %s", session["user_id"], e,
        )
        flash(
            "Servizio mappe temporaneamente non disponibile. Riprovare piu' tardi.",
            "danger",
        )
```

- [ ] **Step 2: Eseguire la suite (no nuovi test, comportamento invariato)**

```bash
.venv\Scripts\python.exe -m pytest -q
```
Expected: 63 passed.

- [ ] **Step 3: Commit**

```bash
git add fdp_app/coordinates/routes.py
git commit -m "feat(coordinates): structured info/warning logging for save/delete events"
```

---

# Fase C — Smoke test e tag

## Task 14: Smoke test manuale + tag `v0.2.0-coordinate`

**Files:** nessuno.

- [ ] **Step 1: Aggiornare `config/workplace.json` con coordinate reali**

Eseguire (operativo, fatto dall'utente):

```powershell
.venv\Scripts\python.exe scripts\set_workplace.py
```

Inserire nome, indirizzo, lat, lon della sede aziendale reale.
Verificare che il JSON sia stato scritto:

```powershell
type config\workplace.json
```

Output atteso: JSON con i valori reali (non piu' Milano 45.4642).

- [ ] **Step 2: Eseguire tutta la suite di test**

```bash
.venv\Scripts\python.exe -m pytest -v
```
Expected: 63 passed.

- [ ] **Step 3: Avviare l'app**

```bash
.venv\Scripts\activate
flask --app app run
```
Expected: `Running on http://127.0.0.1:5010`.

- [ ] **Step 4: Login + visita `/coordinates`**

Browser: `http://127.0.0.1:5010/login`
- Login con un utente FC>60.
- Dalla dashboard, click sulla card "Punto di partenza" -> `/coordinates`.
- Verificare: mappa centrata sulla sede aziendale, marker sulla sede.

- [ ] **Step 5: Selezionare un punto sulla mappa**

- Cliccare un punto a 5-15 km dalla sede.
- Verificare: marker rosso, coordinate visualizzate, indirizzo reverse-geocoded (puo' richiedere qualche secondo).
- Compilare l'etichetta (es. "Casa test").
- Cliccare "Salva punto di partenza".

Expected: redirect a `/coordinates`, banner verde "Punto di partenza salvato.", card con il punto appena salvato, distanza stradale (km da OSRM).

Verificare nel DB:
```sql
SELECT TOP 1 * FROM Employee.fdp.PathTrackCoordinates
WHERE EmployeerHireHistoryId = <tuo_id>
ORDER BY DateSys DESC;
```
Aspettato: una riga con `Coordinates` valorizzato (geography), `RoadKmToWorkplace` non NULL, `DateOut` NULL.

- [ ] **Step 6: Cancellare il punto**

- Cliccare "Cancella punto", confermare il prompt.
- Verificare: redirect a `/coordinates`, banner "Punto di partenza cancellato.", mappa torna interattiva.

Verificare nel DB:
```sql
SELECT TOP 1 DateOut FROM Employee.fdp.PathTrackCoordinates
WHERE EmployeerHireHistoryId = <tuo_id>
ORDER BY DateSys DESC;
```
Aspettato: `DateOut` valorizzato con la data/ora attuale.

- [ ] **Step 7: Test resilienza OSRM**

Disconnettere temporaneamente la rete (o impostare `FDP_OSRM_BASE=http://invalid.local` come env var), riavviare l'app, tentare di salvare un punto.
Expected: flash danger "Servizio mappe temporaneamente non disponibile. Riprovare piu' tardi.", nessun INSERT.

Riconnettere e verificare che il flusso normale torni a funzionare.

- [ ] **Step 8: Tag del Piano 2**

```bash
git tag -a v0.2.0-coordinate -m "Piano 2 - Punto di partenza completato

- Pre-fix Piano 1: logout POST+CSRF, threading.Lock su Database, .env in gitignore, FDP_SECRET_KEY warning, conftest cleanup
- Client OSRM con fallback ORS e cache
- CoordinateRepo con geography::Point CRUD
- CoordinateService orchestration
- /coordinates GET (Leaflet map + reverse geocoding Nominatim) + POST (create/delete)
- 63 test passanti
"
```

- [ ] **Step 9: Push (quando la connettivita' GitHub torna)**

```bash
git push origin main
git push origin v0.2.0-coordinate
```

---

## Definition of Done — Piano 2

- [x] `.env`/`*.env` ignorati; `.flaskenv` tracciato
- [x] Test fixtures chiudono i logging handler
- [x] Logout via POST con CSRF token
- [x] `Database.cursor()` serializzato con `threading.Lock`
- [x] Warning a startup se `FDP_SECRET_KEY` mancante in produzione
- [x] `config/workplace.json` aggiornato con coordinate reali (operativo dall'utente)
- [x] Client OSRM/ORS con cache + test mock
- [x] `CoordinateRepo` con `geography::Point` insert e soft-delete
- [x] `CoordinateService` orchestra routing + repo
- [x] `/coordinates` GET con mappa Leaflet + marker
- [x] Click-to-pick con reverse geocoding Nominatim (browser-side)
- [x] `/coordinates` POST create con validazione lat/lon/label
- [x] `/coordinates/delete` POST con verifica ownership
- [x] Dashboard card linka a `/coordinates`
- [x] 63 test verdi
- [x] Smoke test manuale completato
- [x] Tag `v0.2.0-coordinate` creato

## Prossimi piani

- **Piano 3 — Dichiarazione mensile** (form + calcolo + SP `Registro` + transazioni multi-insert + `flask.g` per per-request DB connection)
- **Piano 4 — Admin** (representable + history + export XLSX)
- **Piano 5 — Notifiche & scheduler** (CLI reminders + email + idempotenza)
