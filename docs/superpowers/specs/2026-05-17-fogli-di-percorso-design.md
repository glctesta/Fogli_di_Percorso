# Fogli di Percorso — Documento di design

**Data:** 2026-05-17
**Stato:** Bozza approvata in brainstorming
**Schema target DB:** `Employee.fdp`

## 1. Scopo e ambito

Web app interna per la gestione mensile dei rimborsi di **carburante** e **corse taxi** dei dipendenti aziendali (datore di lavoro `EmployeerId = 2`).

L'app permette a un dipendente con `FunctionCode > 60` di:

1. registrare il proprio punto di partenza geografico cliccando su una mappa;
2. dichiarare ogni mese (entro il 5 del mese successivo) il numero di viaggi effettuati;
3. caricare i PDF di ricevute e foglio di percorso;
4. ottenere il calcolo automatico del rimborso (carburante) o il totale ricevute (taxi).

Un utente con `FunctionCode > 60` può inoltre **rappresentare** (inserire dati per conto di) i colleghi con `FunctionCode < 60` che condividono lo stesso `SubCdcId`.

L'approvazione e il pagamento (`PathTracks.ReceivedOn`) sono **fuori scope**: vengono gestiti da un sistema a valle.

## 2. Riepilogo delle decisioni di brainstorming

| Tema | Decisione |
|---|---|
| UI | Web app Flask + Leaflet/OpenStreetMap |
| Calcolo distanza | Routing stradale reale via OSRM pubblico (fallback OpenRouteService) |
| Autenticazione | Login app — `NomeUser` + password plain text da `resetservices.dbo.tbuserkey` |
| Filtro accesso | `FunctionCode > 60`, `EndWorkDate IS NULL`, `EmployeerId = 2`, `DateOut IS NULL` |
| Rappresentanza | Utente FC>60 può inserire per dipendenti FC<60 con stesso `SubCdcId`; il campo `InBehalfOfId` su `PathTracks` punta al **rappresentato** |
| Tipo rimborso | Scelto per ogni dichiarazione mensile: `'CARBURANTE'` o `'TAXI'` |
| Formula carburante | `RoadKm * 2 * NumberOfTrips / AvgConsumptionKmL * AvgFuelPriceEurL` |
| Formula taxi | Somma degli importi delle ricevute caricate |
| Valori medi | Tabella nuova `fdp.PathTrackReimbursementRates`, storicizzata per data validità |
| Approvazione | Nessuna in V1. `ReceivedOn` valorizzato da sistema esterno |
| Scadenza | Reminder email il giorno 1, 3 e 5 del mese successivo; blocco rigoroso dopo le 23:59:59 del giorno 5 (Europe/Rome) |
| Sede di lavoro | Unica, in `config/workplace.json` |
| Storage PDF | BLOB `VARBINARY(MAX)` in `fdp.PathTrackDocs.DocumentOfTrackPath` |
| Foglio di percorso | Caricato dall'utente (non generato dall'app) |
| Modifica record | Consentita entro il 5 del mese successivo; dopo è read-only per tutti |
| Funzioni admin | Inserimento per conto, consultazione storico SubCdc, export Excel mensile |
| Scope visibilità | Limitato al proprio `SubCdcId` |
| `RegistryId` | Generato via SP `Employee.dbo.Registro` con `@RegistryTypeId = 790`, `@anno = YEAR(GETDATE())`, `@DataDocumento = GETDATE()`, `@IussedBy = '<cognome nome utente loggato>'`, `@EmployeerId = 2` |
| Email dipendente | `Employee.dbo.EmployeeAddress.WorkEmail` con `DateOut IS NULL` |

## 3. Stack tecnico

- **Backend**: Python 3.11+, Flask 3.x, `pyodbc` (riusa `db_connection.py` e `config_manager.py` esistenti)
- **Frontend**: Jinja2 + Bootstrap 5 (via CDN) + Leaflet 1.9 (via CDN) + JavaScript vanilla
- **Routing distanze**: OSRM pubblico `https://router.project-osrm.org` come default; fallback a OpenRouteService (API key in `settings.py` se valorizzata)
- **Geocoding inverso**: Nominatim (OpenStreetMap) per ottenere l'indirizzo testuale del punto cliccato sulla mappa
- **Email**: `email_connector.py` esistente
- **Scheduler**: Windows Task Scheduler che invoca uno script CLI dell'app
- **Excel**: `openpyxl`
- **Server di produzione**: Waitress dietro IIS (TLS terminato a IIS)
- **Test**: `pytest`, `pytest-cov`, `responses`, `freezegun`

## 4. Architettura

### 4.1 Struttura cartelle

```
fogli_di_percorso/
├── app.py                        # entry-point Flask
├── cli.py                        # comandi: send-reminders, close-month
├── requirements.txt
├── config/
│   ├── workplace.json            # coordinate sede aziendale
│   └── settings.py               # FLASK_SECRET_KEY, OSRM_BASE, ORS_KEY, APP_URL, ...
├── fdp_app/
│   ├── __init__.py               # create_app() factory
│   ├── extensions.py             # session, csrf
│   ├── auth/
│   │   ├── routes.py             # /login, /logout
│   │   ├── service.py            # check_password(), load_user_context()
│   │   └── decorators.py         # @login_required, @same_subcdc_required, @deadline_open
│   ├── coordinates/
│   │   ├── routes.py             # GET/POST /coordinates
│   │   ├── service.py            # selezione/cancellazione punto, calcolo RoadKm
│   │   └── templates/coordinates/
│   ├── pathtracks/
│   │   ├── routes.py             # /pathtracks/new, /pathtracks/<id>, /pathtracks/list
│   │   ├── service.py            # calcolo rimborso, validazione scadenza
│   │   ├── routing.py            # client OSRM/ORS con cache in-memory
│   │   └── templates/pathtracks/
│   ├── admin/
│   │   ├── routes.py             # /admin/representable, /admin/history, /admin/export
│   │   └── templates/admin/
│   ├── notifications/
│   │   ├── service.py            # send_reminder_email(), close_month_report()
│   │   └── templates/reminder.html
│   ├── repos/
│   │   ├── employee_repo.py
│   │   ├── coordinate_repo.py
│   │   ├── pathtrack_repo.py
│   │   ├── doc_repo.py
│   │   ├── rate_repo.py
│   │   └── registry_repo.py
│   ├── static/
│   └── templates/
└── tests/
```

### 4.2 Pattern

- **Repository**: ogni `*_repo.py` contiene tutto il SQL della propria entità. Le route e i service non vedono SQL.
- **Service**: logica di business (calcolo rimborso, validazione, orchestrazione multi-repo). Riceve la connection injectata per testabilità.
- **Routes**: orchestrano richiesta HTTP → service → render. Pochissima logica.

## 5. Schema database

### 5.1 Tabelle esistenti utilizzate in lettura

| Tabella | Uso |
|---|---|
| `Employee.dbo.Employees` | nome, cognome, `EmployeeId` |
| `Employee.dbo.EmployeeHireHistory` | filtro `EndWorkDate IS NULL` e `EmployeerId = 2`, sorgente di `EmployeeHireHistoryId` |
| `Employee.dbo.EmployeeCdcStories` | `SubCdcId`, `FunctionId`, con `DateOut IS NULL` |
| `Employee.dbo.CdcSub` | descrizione del SubCdc |
| `Employee.dbo.Functions` | `FunctionCode` (>60 per login, <60 per rappresentati) |
| `Employee.dbo.EmployeeAddress` | `WorkEmail` con `DateOut IS NULL` |
| `resetservices.dbo.tbuserkey` | `NomeUser`, `pass` (plain text) per autenticazione |
| `Employee.dbo.Registro` (SP) | generazione `RegistryId` |

### 5.2 Tabelle esistenti scritte dall'app (schema `fdp`)

#### `fdp.PathTrackCoordinates`
Punto di partenza del dipendente. Esiste un solo punto attivo per dipendente (`DateOut IS NULL`).

- `EmployeerHireHistoryId` punta al **dipendente** titolare del punto (rappresentato in caso di delega).
- `Coordinates` è di tipo `geography`: `geography::Point(lat, lon, 4326)`.
- Cancellazione logica con `DateOut = GETDATE()`.

**Aggiunta a tabella esistente:**
```sql
ALTER TABLE Employee.fdp.PathTrackCoordinates
    ADD RoadKmToWorkplace DECIMAL(9,3) NULL;
```
Valorizzato al momento del salvataggio del punto con il risultato di OSRM/ORS.

#### `fdp.PathTracks`
Dichiarazione mensile.

- `EmployeeHireHistoryId` = chi inserisce (utente loggato)
- `RegistryId` = ritorno della SP `Employee.dbo.Registro`
- `DatePathTrack` = primo giorno del mese di riferimento (es. `2026-04-01` per la dichiarazione di aprile)
- `DeclaratedPathId` = FK a `PathTrackCoordinates.PathTrackCoordinateId` (punto di partenza usato)
- `InBehalfOfId` = `EmployeeHireHistoryId` del **rappresentato**; `NULL` se l'inserimento è per sé
- `ReceivedOn` = sempre `NULL` dall'app

**Aggiunte a tabella esistente:**
```sql
ALTER TABLE Employee.fdp.PathTracks
    ADD ReimbursementType  CHAR(10)      NOT NULL,         -- 'CARBURANTE' | 'TAXI'
        NumberOfTrips      INT           NOT NULL,
        RoadKm             DECIMAL(9,3)  NOT NULL,         -- one-way al momento dell'inserimento
        RateIdUsed         INT           NULL,             -- FK PathTrackReimbursementRates (NULL per TAXI)
        TaxiTotalEur       DECIMAL(9,2)  NULL,             -- somma ricevute (solo TAXI)
        ComputedAmountEur  DECIMAL(9,2)  NOT NULL,         -- importo finale congelato
        DateOut            DATETIME      NULL;             -- soft delete
```

#### `fdp.PathTrackDocs`
PDF caricati (BLOB).

- `DocumentOfTrackPath` = `VARBINARY(MAX)` (contiene il binario del PDF)
- `DocTitle` = etichetta umana (es. `"Ricevuta distributore - 2026-04-12"`, `"Foglio di Percorso aprile 2026"`)
- `PathTrackId` = FK a `PathTracks`

**Aggiunta a tabella esistente:**
```sql
ALTER TABLE Employee.fdp.PathTrackDocs
    ADD DateOut DATETIME NULL;
```

### 5.3 Tabella nuova

```sql
CREATE TABLE Employee.fdp.PathTrackReimbursementRates (
    RateId              INT IDENTITY(1,1) PRIMARY KEY,
    AvgConsumptionKmL   DECIMAL(6,2) NOT NULL,   -- km/litro accettato
    AvgFuelPriceEurL    DECIMAL(6,3) NOT NULL,   -- euro/litro
    ValidFrom           DATE NOT NULL,
    ValidTo             DATE NULL,               -- NULL = corrente
    DateSys             DATETIME NOT NULL DEFAULT GETDATE(),
    UserSys             NVARCHAR(100) NOT NULL
);
CREATE UNIQUE INDEX UX_Rates_ValidFrom
    ON Employee.fdp.PathTrackReimbursementRates(ValidFrom);
```

Lookup del rate per un viaggio:
```sql
SELECT TOP 1 RateId, AvgConsumptionKmL, AvgFuelPriceEurL
FROM Employee.fdp.PathTrackReimbursementRates
WHERE ValidFrom <= @DatePathTrack
  AND (ValidTo IS NULL OR ValidTo >= @DatePathTrack)
ORDER BY ValidFrom DESC;
```

### 5.4 Indici aggiuntivi

```sql
CREATE INDEX IX_PathTracks_Behalf_Date
    ON Employee.fdp.PathTracks (
        COALESCE(InBehalfOfId, EmployeeHireHistoryId),
        DatePathTrack
    )
    WHERE DateOut IS NULL;

CREATE INDEX IX_PathTrackCoordinates_Emp_Out
    ON Employee.fdp.PathTrackCoordinates (EmployeerHireHistoryId, DateOut);
```

## 6. Flussi utente

### 6.1 Login
Query autenticazione:
```sql
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
WHERE k.NomeUser = ?;
```
Confronto `pass` plain text. Verifica `FunctionCode > 60`. Salvataggio in `session`: `EmployeeHireHistoryId`, `SubCdcId`, `FunctionCode`, `full_name`.

### 6.2 Setup punto di partenza
1. `GET /coordinates` mostra mappa Leaflet centrata sull'Italia (o sull'ultima posizione nota).
2. L'utente clicca un punto. JS cattura `{lat, lon}` e chiede geocoding inverso a Nominatim per mostrare l'indirizzo.
3. `POST /coordinates` con `{lat, lon, label}`.
4. Service:
   - rifiuta se esiste già un punto attivo (`DateOut IS NULL`) per il target; in tal caso l'utente deve prima cancellare;
   - chiama OSRM per ottenere `RoadKmToWorkplace`;
   - `INSERT INTO fdp.PathTrackCoordinates (..., Coordinates, RoadKmToWorkplace, DateOut, DateSys) VALUES (..., geography::Point(?, ?, 4326), ?, NULL, GETDATE())`.

Cancellazione: bottone "Cancella punto" → `UPDATE fdp.PathTrackCoordinates SET DateOut = GETDATE() WHERE PathTrackCoordinateId = ?`.

### 6.3 Dichiarazione mensile per sé
1. `GET /pathtracks/new` calcola `DatePathTrack = primo giorno del mese precedente`.
2. Verifica scadenza (oggi ≤ giorno 5 del mese corrente, Europe/Rome).
3. Verifica esistenza dichiarazione attiva: se esiste → redirect a `/pathtracks/<id>/edit`.
4. Carica punto di partenza attivo (sennò → redirect a `/coordinates`).
5. Mostra form: tipo rimborso (radio), numero viaggi, ricevute (se TAXI), upload PDF.
6. JS calcola anteprima live dell'importo via fetch a `/pathtracks/preview`.
7. `POST /pathtracks` esegue la transazione descritta nella sezione 7.

### 6.4 Dichiarazione per conto di un rappresentato
- `/admin/representable` elenca i dipendenti con stesso `SubCdcId` e `FunctionCode < 60`.
- Click su un nome → `/pathtracks/new?on_behalf_of=<EmployeeHireHistoryId>`.
- Il service imposta `InBehalfOfId = on_behalf_of`, `EmployeeHireHistoryId = utente loggato`.
- Il rappresentante può anche gestire il punto di partenza del rappresentato (`/coordinates?on_behalf_of=<id>`).

### 6.5 Modifica e cancellazione (entro il 5)
- `/pathtracks/<id>/edit`: form precompilato.
- `/pathtracks/<id>/delete`: soft delete (`DateOut = GETDATE()`).
- Dopo il 5: bottoni nascosti, route ritornano 403.

### 6.6 Storico e export (scope = proprio `SubCdcId`)
- `/admin/history`: tabella filtrabile (mese, anno, tipo, dipendente).
- `/admin/export?year=2026&month=04`: XLSX generato in memoria con `openpyxl`.

### 6.7 Logout
`/logout` distrugge la session e fa redirect a `/login`.

## 7. Regole di business

### 7.1 Calcolo rimborso

**Carburante**
```
ComputedAmountEur = ROUND(
    (RoadKm * 2 * NumberOfTrips / AvgConsumptionKmL) * AvgFuelPriceEurL,
    2
)
```
**Taxi**
```
ComputedAmountEur = somma(ricevuta.importo)
TaxiTotalEur = ComputedAmountEur
```
L'importo è **congelato** al salvataggio. Cambi successivi del rate non ricalcolano record passati.

### 7.2 Validazioni server-side

| Controllo | Reazione |
|---|---|
| Punto di partenza attivo esiste per il target | sennò errore |
| Scadenza aperta (entro il 5, Europe/Rome) | sennò 403 |
| `1 <= NumberOfTrips <= 31` | sennò errore |
| `ReimbursementType ∈ {'CARBURANTE','TAXI'}` | sennò 400 |
| Se TAXI: almeno una ricevuta con importo > 0 | sennò errore |
| Se CARBURANTE: rate valido esiste | sennò 500 + log |
| Almeno 1 PDF "Foglio di Percorso" | sennò errore |
| Almeno 1 PDF "Ricevuta" del tipo corrispondente | sennò errore |
| PDF valido (magic bytes `%PDF-`, max 5 MB, max 20 file) | sennò errore |
| Niente dichiarazione attiva duplicata stesso target/mese | sennò redirect a edit |
| Delega: target stesso `SubCdcId`, `FC < 60` | sennò 403 |

### 7.3 Transazione di inserimento

```
BEGIN TRAN
  1. EXEC Employee.dbo.Registro @RegistryTypeId=790,
                                @anno=YEAR(GETDATE()),
                                @DataDocumento=GETDATE(),
                                @IussedBy=<cognome nome>,
                                @EmployeerId=2
     -> @new_registry_id
  2. INSERT INTO fdp.PathTracks (...) VALUES (..., @new_registry_id, ...)
     OUTPUT INSERTED.PathTrackId -> @new_path_track_id
  3. Per ogni PDF caricato:
       INSERT INTO fdp.PathTrackDocs (DocumentOfTrackPath, DocTitle, PathTrackId, DateSys)
       VALUES (?, ?, @new_path_track_id, GETDATE())
COMMIT
```
Failure su qualunque step → ROLLBACK.

### 7.4 Cancellazione logica
- `PathTrackCoordinates.DateOut = GETDATE()` per sostituire il punto di partenza.
- `PathTracks.DateOut = GETDATE()` per annullare una dichiarazione (consentito solo entro il 5).
- `PathTrackDocs.DateOut = GETDATE()` per rimuovere un singolo allegato in fase di modifica.

### 7.5 Caching OSRM
Cache in-memory `(lat, lon) -> road_km` di sessione. Il valore viene comunque persistito su `PathTrackCoordinates.RoadKmToWorkplace`.

### 7.6 Timezone
Tutto Europe/Rome lato app. DB usa `GETDATE()` (server time). La verifica scadenza usa `datetime.now(ZoneInfo("Europe/Rome"))`.

## 8. Reminder e scheduler

### 8.1 Comando CLI
```
python -m fdp_app.cli send-reminders --stage={opening|midway|last-call}
python -m fdp_app.cli close-month
```

### 8.2 Schedulazione Windows Task Scheduler

| Quando (Europe/Rome) | Task |
|---|---|
| giorno 1 alle 09:00 | `send-reminders --stage=opening` |
| giorno 3 alle 09:00 | `send-reminders --stage=midway` |
| giorno 5 alle 09:00 | `send-reminders --stage=last-call` |
| giorno 6 alle 02:00 | `close-month` (report mancanti) |

### 8.3 Logica `send-reminders`
1. `target_month = mese precedente alla data corrente`.
2. Query candidati: dipendenti con `FC > 60`, attivi, `EmployeerId = 2`, con `WorkEmail` da `EmployeeAddress`.
3. Per ognuno: verifica se esiste `PathTracks` attivo per `target_month` (per sé o come `InBehalfOfId`).
4. Se mancante → email via `email_connector.EmailSender`.
5. Log su file. Idempotenza tramite file di stato `state/reminders-YYYY-MM-DD-{stage}.done`.

### 8.4 Email template
Template Jinja `notifications/templates/reminder.html`, parametri `Cognome`, `Nome`, `MESE_SCADUTO`, `MESE_CORRENTE`, `APP_URL`. Subject diverso per stage.

### 8.5 Blocco scadenza (applicativo)
```python
def is_open_for_month(date_path_track: date) -> bool:
    tz = ZoneInfo("Europe/Rome")
    now = datetime.now(tz)
    next_month_first = (date_path_track + relativedelta(months=1)).replace(day=1)
    window_open  = datetime.combine(next_month_first, time(0, 0, 0), tzinfo=tz)
    window_close = datetime.combine(
        next_month_first.replace(day=5), time(23, 59, 59), tzinfo=tz
    )
    return window_open <= now <= window_close
```
Decoratore `@deadline_open` su tutti gli endpoint di scrittura.

## 9. Error handling

| Caso | Strategia |
|---|---|
| DB connection down | retry-once; al secondo fallimento 503 + log |
| OSRM down | fallback ORS; se entrambi falliti → blocco salvataggio punto |
| SP `Registro` fallisce | ROLLBACK, errore generico, log dettagliato |
| PDF malformato | rifiuto in validazione, messaggio chiaro |
| Eccezione non gestita | error page 500, log + traceback |
| 404/403/400 | template dedicati in italiano |
| CSRF | Flask-WTF su tutti i POST |

Logging via `logging` con file rotante `logs/app-YYYY-MM-DD.log`.

## 10. Sicurezza

| Area | Mitigazione |
|---|---|
| Password plain text (vincolo legacy) | HTTPS obbligatorio, niente log della password, session cookie `Secure`/`HttpOnly`/`SameSite=Lax`, timeout 8h |
| SQL injection | tutti i query parametrici (`?`), zero string concat |
| XSS | Jinja auto-escape ON; mai `\|safe` su input utente |
| CSRF | Flask-WTF token su tutti i form |
| Upload PDF | magic bytes `%PDF-`, content-type, max 5 MB/file, max 20 file/dichiarazione, `DocTitle` sanitizzato |
| Autorizzazione orizzontale | ogni route con `id` verifica appartenenza al target legittimo |
| Rate limit login | 5 tentativi/15min per `NomeUser` → blocco temporaneo in-memory |
| Secret Flask | letto da `config_manager` come le altre credenziali |
| Log | mai PII a livello INFO, solo `EmployeeHireHistoryId` |

## 11. Testing

### 11.1 Unit
- `test_pathtracks_service.py`: formula carburante (varianti), somma taxi, arrotondamento.
- `test_deadline.py`: scenari di apertura/chiusura, edge case fine mese e fine anno.
- `test_validation.py`: ogni regola della sezione 7.2.
- `test_routing.py`: client OSRM con `responses`, fallback ORS, cache.

### 11.2 Integrazione repository
DB di staging dedicato, fixture `pytest` in transazione. Test su insert/select/soft-delete per ogni repo.

### 11.3 End-to-end (`flask test_client`)
- `test_login_flow.py`: login OK, login non autorizzato (`FC ≤ 60`), login fallito, rate limit.
- `test_pathtracks_flow.py`: nuovo punto → dichiarazione → modifica → cancellazione, con `freezegun`.
- `test_admin_flow.py`: rappresentante inserisce per rappresentato, scope `SubCdcId`, export Excel.

### 11.4 Coverage
Target ≥80% sui moduli `service` e `repos`.

## 12. Deploy

- **Sviluppo**: `flask run`, DB staging.
- **Produzione**: Waitress dietro IIS con ARR + TLS terminato a IIS.
- **Cartelle scritte**: `logs/`, `state/` (fuori dalla cartella statica).
- **Configurazione**: `config/workplace.json` + `config/settings.py` (versionati senza segreti) + file `.enc/.key` esistenti per credenziali DB/email (NON in git).
- **Requirements**: `flask`, `flask-wtf`, `pyodbc`, `requests`, `openpyxl`, `python-dateutil`, `cryptography`, `waitress`, `tzdata`. Dev: `pytest`, `pytest-cov`, `responses`, `freezegun`.
- **Runbook**: `docs/install.md` con passi setup IIS, Task Scheduler, copia file enc.

## 13. Out of scope (V1)

- Workflow di approvazione (`ReceivedOn` lasciato a sistema esterno).
- Generazione automatica del PDF "Foglio di Percorso".
- API REST esposta a sistemi esterni.
- Multi-sede di lavoro.
- Multi-lingua.
- Mobile-first / responsive avanzato (responsive baseline Bootstrap).
- Audit log dettagliato delle modifiche (oltre a `DateSys`/`DateOut`).

## 14. Glossario

| Termine | Significato |
|---|---|
| **Rappresentante** | Utente loggato (`FC > 60`) che inserisce dati per un altro dipendente |
| **Rappresentato** | Dipendente (`FC < 60`, stesso `SubCdcId`) per cui un altro utente inserisce dati. `InBehalfOfId` = `EmployeeHireHistoryId` del rappresentato |
| **Rate** | Coppia (consumo medio km/l, prezzo medio €/l) valida per un periodo |
| **DatePathTrack** | Primo giorno del mese di riferimento della dichiarazione |
| **Finestra di scadenza** | Dal giorno 1 alle 00:00 al giorno 5 alle 23:59:59 del mese successivo a `DatePathTrack` |
