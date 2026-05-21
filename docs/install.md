# Install — Fogli di Percorso

Runbook di deployment dell'applicazione intranet **Fogli di Percorso** (Flask 3 + Waitress + IIS) sul server Windows di Vandewiele Romania.

Questo documento e' destinato a un operatore IT che conosce Windows Server, IIS e SQL Server, ma non conosce Flask o questo codice. Seguito passo-passo, permette un deploy riproducibile da zero.

Per architettura applicativa, flussi utente e dettagli interni: vedi `PRODUCT.md` e `DESIGN.md`.

---

## 1. Prerequisiti server Windows

Prima di iniziare assicurarsi che il server abbia tutti i componenti elencati. Le versioni indicate sono i minimi testati.

| Componente | Versione | Note / Link |
|---|---|---|
| Windows Server | 2019 o superiore | Per staging va bene anche Windows 10/11 Pro |
| Python | 3.11+ | <https://www.python.org/downloads/windows/> — durante l'installazione selezionare **"Add python.exe to PATH"** |
| Microsoft ODBC Driver for SQL Server | 18 | <https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server> |
| IIS | feature server standard | Abilitare tramite **Server Manager > Add Roles and Features > Web Server (IIS)** |
| IIS `httpPlatformHandler` | 1.2+ | <https://www.iis.net/downloads/microsoft/httpplatformhandler> — necessario per il reverse-proxy verso Waitress |
| Git per Windows | 2.40+ | <https://git-scm.com/download/win> — usato per clone iniziale e aggiornamenti |
| TLS certificate | aziendale | Certificato del dominio `*.vandewiele.local` importato nello store IIS |

### Servizi e accessi richiesti

- **SMTP relay / Outlook** configurato per il modulo `email_connector`. La configurazione SMTP risiede **fuori** da questo repo (vedi `email_connector.py` e i file `email_credentials.enc` / `email_key.key`).
- **SQL Server** raggiungibile dal server applicativo, con un account che abbia:
  - `SELECT`, `INSERT`, `UPDATE`, `DELETE` sullo schema `Employee.fdp`
  - `EXECUTE` sulla stored procedure `Employee.dbo.Registro`
  - `SELECT` sulle tabelle anagrafiche `Employee.dbo.*` usate dall'app (es. impiegati, sedi)

---

## 2. Installazione applicazione

Aprire una console **PowerShell come amministratore** ed eseguire:

```powershell
git clone https://github.com/glctesta/Fogli_di_Percorso.git C:\inetpub\fdp
cd C:\inetpub\fdp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Creare le cartelle di runtime se non gia' presenti:

```powershell
New-Item -ItemType Directory -Force -Path C:\inetpub\fdp\logs
New-Item -ItemType Directory -Force -Path C:\inetpub\fdp\state
```

Configurare le credenziali del database (script interattivo gia' presente nel repo — chiede host, database, utente, password e li cifra in `db_config.enc`):

```powershell
python scripts\configure_db.py
```

Risultato atteso: il file `C:\inetpub\fdp\db_config.enc` viene creato/aggiornato. Conservarne un backup (vedi sezione 9): senza la chiave `encryption_key.key` non e' recuperabile.

---

## 3. Migrazioni SQL

L'ordine di esecuzione **e' obbligatorio**. Aprire SSMS, connettersi al database `Employee` con un utente con diritti DDL, ed eseguire gli script nella seguente sequenza:

```sql
-- 1) Tabelle base: PathTrackCoordinates, PathTracks, PathTrackDocs, PathTrackReimbursementRates
:r C:\inetpub\fdp\sql\001_init.sql

-- 2) Colonna Status (default 'DRAFT') sulla tabella PathTracks
:r C:\inetpub\fdp\sql\002_add_status.sql

-- 3) Tabella BnrRates per la cache del tasso di cambio BNR
:r C:\inetpub\fdp\sql\004_create_bnrrates.sql
```

In alternativa, aprire ciascun file in SSMS e lanciarlo con `F5`.

Note importanti:

- **Tutti gli script sono idempotenti** (usano `IF NOT EXISTS` / `IF COL_LENGTH IS NULL`): possono essere ri-eseguiti senza danni.
- **Non esiste `003_*.sql`**: il salto di numerazione e' voluto e non indica uno script mancante.
- Per verifica rapida post-migrazione:

```sql
SELECT name FROM Employee.sys.tables
WHERE schema_id = SCHEMA_ID('fdp')
ORDER BY name;
```

Risultato atteso: almeno `PathTrackCoordinates`, `PathTrackDocs`, `PathTrackReimbursementRates`, `PathTracks`, `BnrRates`.

---

## 4. Configurazione environment variables

Impostare le variabili a livello **macchina** (visibili al processo IIS) tramite **Pannello di controllo > Sistema > Impostazioni di sistema avanzate > Variabili d'ambiente** oppure con `setx /M` da PowerShell amministratore.

| Variabile | Valore | Note |
|---|---|---|
| `FDP_SECRET_KEY` | stringa random 32+ char | Chiave di firma delle sessioni Flask. Generare una volta sola e conservarla. |
| `FDP_COOKIE_SECURE` | `1` | Obbligatorio in produzione (TLS gestito da IIS). In dev locale lasciare `0`. |
| `FDP_APP_URL` | `https://fdp.vandewiele.local` | URL base usato nei link delle email reminder. |
| `FDP_SMTP_HOST` | host SMTP relay | Solo se `email_connector` legge da env. Vedi il suo README interno. |
| `FDP_SMTP_PORT` | `25` o `587` | Idem. |
| `FDP_SMTP_FROM` | `fdp-noreply@vandewiele.com` | Idem. |

Generare una `FDP_SECRET_KEY` sicura:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Impostarla da PowerShell amministratore:

```powershell
setx /M FDP_SECRET_KEY "<incollare-qui-il-valore-generato>"
setx /M FDP_COOKIE_SECURE "1"
setx /M FDP_APP_URL "https://fdp.vandewiele.local"
```

> Dopo `setx /M` e' necessario riavviare il sito IIS (o il server) perche' i nuovi processi figli ereditino le variabili.

---

## 5. Avvio Waitress dietro IIS

Architettura runtime:

- **Waitress** e' il WSGI server Python che esegue effettivamente l'app (`fdp_app:create_app`).
- **IIS** termina TLS (porta 443), gestisce il certificato aziendale, e inoltra le richieste a Waitress su `127.0.0.1:5010` tramite `httpPlatformHandler`.

### File `web.config`

Creare `C:\inetpub\fdp\web.config` con questo contenuto:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <system.webServer>
    <handlers>
      <add name="httpPlatformHandler" path="*" verb="*"
           modules="httpPlatformHandler" resourceType="Unspecified" />
    </handlers>
    <httpPlatform processPath="C:\inetpub\fdp\.venv\Scripts\python.exe"
                  arguments="-m waitress --listen=*:5010 fdp_app:create_app"
                  stdoutLogEnabled="true"
                  stdoutLogFile="C:\inetpub\fdp\logs\iis-stdout"
                  startupTimeLimit="60"
                  requestTimeout="00:04:00">
      <environmentVariables>
        <environmentVariable name="FLASK_ENV" value="production" />
      </environmentVariables>
    </httpPlatform>
  </system.webServer>
</configuration>
```

### Configurazione sito IIS

In **IIS Manager**:

1. **Sites > Add Website**
   - Site name: `fdp`
   - Physical path: `C:\inetpub\fdp`
   - Binding: `https`, porta `443`, hostname `fdp.vandewiele.local`, certificato TLS aziendale
2. **Application Pools > fdp**
   - .NET CLR version: **No Managed Code**
   - Identity: `LocalSystem` **oppure** un service account con accesso al DB SQL Server (raccomandato per audit)
   - Start Mode: `AlwaysRunning`
3. Verificare che l'identita' del pool abbia `Read & Execute` su `C:\inetpub\fdp` e `Modify` su `C:\inetpub\fdp\logs` e `C:\inetpub\fdp\state`.

Test rapido (dal server stesso):

```powershell
Invoke-WebRequest -UseBasicParsing https://fdp.vandewiele.local/ -SkipCertificateCheck
```

Risultato atteso: HTTP 200 (o 302 verso `/auth/login`).

---

## 6. Task Scheduler — 5 task pianificati

L'app esegue 5 job batch via `python -m fdp_app.cli`. Ognuno deve essere registrato come Scheduled Task con le seguenti impostazioni comuni:

- **Run whether user is logged on or not** (richiede password dell'account)
- **Run with highest privileges**
- **Working directory** (campo "Start in"): `C:\inetpub\fdp`
- **Program/script**: `C:\inetpub\fdp\.venv\Scripts\python.exe`

### Riepilogo dei 5 task

#### a. `fdp-reminder-opening`

| | |
|---|---|
| Nome | `fdp-reminder-opening` |
| Trigger | Mensile, giorno 1 di ogni mese, ore 09:00 |
| Comando | `python.exe -m fdp_app.cli send-reminders --stage=opening` |
| Working dir | `C:\inetpub\fdp` |

#### b. `fdp-reminder-midway`

| | |
|---|---|
| Nome | `fdp-reminder-midway` |
| Trigger | Mensile, giorno 3 di ogni mese, ore 09:00 |
| Comando | `python.exe -m fdp_app.cli send-reminders --stage=midway` |
| Working dir | `C:\inetpub\fdp` |

#### c. `fdp-reminder-last-call`

| | |
|---|---|
| Nome | `fdp-reminder-last-call` |
| Trigger | Mensile, giorno 5 di ogni mese, ore 09:00 |
| Comando | `python.exe -m fdp_app.cli send-reminders --stage=last-call` |
| Working dir | `C:\inetpub\fdp` |

#### d. `fdp-close-month`

| | |
|---|---|
| Nome | `fdp-close-month` |
| Trigger | Mensile, giorno 6 di ogni mese, ore 02:00 |
| Comando | `python.exe -m fdp_app.cli close-month` |
| Working dir | `C:\inetpub\fdp` |

#### e. `fdp-bnr-refresh`

| | |
|---|---|
| Nome | `fdp-bnr-refresh` |
| Trigger | Settimanale, da Lunedi a Venerdi, ore 09:00 |
| Comando | `python.exe -m fdp_app.cli refresh-bnr-rate` |
| Working dir | `C:\inetpub\fdp` |

### Snippet PowerShell di esempio

Eseguire da PowerShell **come amministratore**. Lo snippet crea `fdp-reminder-opening`: copiarlo e adattarlo (nome, argomento `--stage`, trigger) per gli altri 4.

```powershell
$action = New-ScheduledTaskAction `
  -Execute "C:\inetpub\fdp\.venv\Scripts\python.exe" `
  -Argument "-m fdp_app.cli send-reminders --stage=opening" `
  -WorkingDirectory "C:\inetpub\fdp"

$trigger = New-ScheduledTaskTrigger -Monthly -DaysOfMonth 1 -At 9:00am

$principal = New-ScheduledTaskPrincipal `
  -UserId "VANDEWIELE\svc-fdp" `
  -LogonType Password `
  -RunLevel Highest

$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -StartWhenAvailable `
  -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask `
  -TaskName "fdp-reminder-opening" `
  -Action $action `
  -Trigger $trigger `
  -Principal $principal `
  -Settings $settings `
  -Description "FDP: invio reminder iniziale mensile (giorno 1)"
```

Per gli altri task:

- `fdp-reminder-midway` → trigger `-Monthly -DaysOfMonth 3 -At 9:00am`, argument `... --stage=midway`
- `fdp-reminder-last-call` → trigger `-Monthly -DaysOfMonth 5 -At 9:00am`, argument `... --stage=last-call`
- `fdp-close-month` → trigger `-Monthly -DaysOfMonth 6 -At 2:00am`, argument `-m fdp_app.cli close-month`
- `fdp-bnr-refresh` → trigger `New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 9:00am`, argument `-m fdp_app.cli refresh-bnr-rate`

> L'account `VANDEWIELE\svc-fdp` nell'esempio e' indicativo: sostituire con il service account aziendale che ha accesso al DB. La password verra' chiesta interattivamente da `Register-ScheduledTask` se non si usa `-Password`.

---

## 7. Log, rotazione, monitoring

### File di log e stato

| Percorso | Contenuto | Rotazione |
|---|---|---|
| `C:\inetpub\fdp\logs\cli.log` | Output dei task batch (`send-reminders`, `close-month`, `refresh-bnr-rate`, `health-check`) | Manuale (TODO: `RotatingFileHandler` in v0.7) |
| `C:\inetpub\fdp\logs\app.log` | Log applicativo Flask in runtime | Manuale |
| `C:\inetpub\fdp\logs\iis-stdout*.log` | stdout/stderr del processo Python sotto IIS, scritto da `httpPlatformHandler` | Automatica (un file per avvio del processo) |
| `C:\inetpub\fdp\state\reminders-YYYY-MM-DD-{stage}.done` | Summary JSON dell'invio reminder (audit trail) | Conservare 90 giorni |
| `C:\inetpub\fdp\state\missing-YYYY-MM.xlsx` | Report XLSX dei dipendenti senza dichiarazione a fine mese (recuperato manualmente dall'HR) | Conservare 90 giorni |

### Monitoring

- **Task Scheduler**: per ognuno dei 5 task, controllare la colonna **Last Run Result**. Valore atteso: `0x0` (success). Qualsiasi valore diverso da zero → consultare `C:\inetpub\fdp\logs\cli.log`.
- **IIS**: il sito `fdp` deve essere in stato `Started`. Se `httpPlatformHandler` non riesce ad avviare Python, l'errore appare in `iis-stdout*.log`.
- **Salute applicativa**: lanciare periodicamente

```powershell
C:\inetpub\fdp\.venv\Scripts\python.exe -m fdp_app.cli health-check
```

  Exit code `0` = OK, qualunque altro valore = problema (probabilmente DB irraggiungibile).

### Pulizia manuale log (placeholder fino a v0.7)

Esempio script di pulizia da pianificare separatamente se i log crescono:

```powershell
Get-ChildItem C:\inetpub\fdp\logs\iis-stdout*.log |
  Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
  Remove-Item -Force
```

---

## 8. Verifica installazione

Checklist di smoke test da eseguire dopo ogni deploy o aggiornamento.

1. **Web UI raggiungibile**

```powershell
Invoke-WebRequest -UseBasicParsing https://fdp.vandewiele.local/
```

   Apre la pagina di login Flask (HTTP 200 o redirect verso `/auth/login`).

2. **Health-check applicativo**

```powershell
cd C:\inetpub\fdp
.\.venv\Scripts\python.exe -m fdp_app.cli health-check
echo $LASTEXITCODE
```

   Atteso: `0` e in `cli.log` la riga `health-check OK: db ping, rates_count=<N>`.

3. **Database accessibile** (in SSMS connesso a `Employee`):

```sql
SELECT TOP 5 *
FROM Employee.fdp.PathTracks
ORDER BY DateIn DESC;
```

   La query deve completare senza errori (anche se restituisce 0 righe su un'installazione vergine).

4. **Invio reminder di test** (preferibilmente verso un destinatario di test, oppure con il proprio indirizzo nell'anagrafica):

```powershell
.\.venv\Scripts\python.exe -m fdp_app.cli send-reminders --stage=opening
```

   Verificare la ricezione dell'email e controllare `cli.log` per la riga `send-reminders opening: sent=<N>, skipped=<M>`.

5. **Task Scheduler** — eseguire una volta manualmente uno dei 5 task tramite `Run` da Task Scheduler, e verificare `Last Run Result = 0x0`.

---

## 9. Backup — raccomandazioni

| Cosa | Frequenza | Note |
|---|---|---|
| Database `Employee` (intero) | Backup completo notturno + log shipping | Lo schema `fdp` vive dentro `Employee`. Confermare con il DBA che il backup esistente di `Employee` includa gia' lo schema `fdp`. |
| `C:\inetpub\fdp\state\` | Notturno | Contiene l'audit trail dei reminder (`.done` JSON) e i report XLSX HR. |
| `C:\inetpub\fdp\db_config.enc` | One-shot dopo `configure_db.py`, e ad ogni rotazione credenziali | **Irreplaceable** se perso: senza di esso l'app non sa come connettersi al DB. Conservare anche `encryption_key.key`. |
| `C:\inetpub\fdp\web.config` | One-shot | Piccolo, ma utile averlo nel backup di configurazione del server. |
| Variabili d'ambiente `FDP_*` | Documentare in vault aziendale | Soprattutto `FDP_SECRET_KEY`: rigenerarla invalida tutte le sessioni utente attive. |
| Codice sorgente | Sempre disponibile | Tracciato in GitHub: <https://github.com/glctesta/Fogli_di_Percorso.git> |

Per disaster recovery completo (perdita server) fare riferimento alla procedura aziendale standard di ripristino server Windows + IIS + SQL Server; questo runbook copre solo il deploy della singola applicazione.
