# Fogli di Percorso — Piano 6: Notifiche email + Scheduler

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Aggiungere il sistema di **reminder email** (3 stage di promemoria nei
giorni 1, 3, 5 del mese successivo a chi non ha ancora inviato), il comando
**close-month** (genera report XLSX dei mancanti dopo il 5), un **job notturno BNR**
per pre-caricare i tassi giornalieri, e il **runbook Windows Task Scheduler** per
deploy. Ogni dipendente FC>60 con email valida nella tabella `EmployeeAddress`
riceve i reminder nella propria lingua preferita.

**Architecture:**
- `fdp_app/cli.py` con `argparse` espone 4 sotto-comandi: `send-reminders`,
  `close-month`, `refresh-bnr-rate`, `health-check`
- `EmailReminderService` orchestrato (legge candidati, formatta email da
  template Jinja, invia via `email_connector.EmailSender`, scrive file di stato
  per idempotenza in `state/`)
- `EmployeeRepo` esteso con `find_pending_for_month(...)` (lista FC>60
  attivi senza `PathTracks` SUBMITTED per il mese di riferimento)
- `MonthCloser` genera XLSX `state/missing-YYYY-MM.xlsx` con i pendenti
- `BnrRefreshJob` invoca `CurrencyService.resolve_for(date.today())` per
  pre-popolare il tasso giornaliero
- `docs/install.md` documenta le 4 attività schedulate Windows

**Tech Stack:** Python stdlib (argparse), `email_connector.EmailSender` esistente,
Jinja2 (gia' caricato via Flask), `openpyxl` (gia' in requirements),
`freezegun` per test, Windows Task Scheduler per runtime (documentato).

**Riferimento spec:** Sezione 8 (Reminder e scheduler). Aggiungere §8.5 (close-month).

**Prerequisito:** Piano 5 + audit polish completati. Tag `v0.5.0-i18n-currency`
+ commit `1559eb0` (P2 batch). 251 test verdi.

---

## Regole di business

| Aspetto | Regola |
|---|---|
| **Mese di riferimento** | `previous_month_first_day()` (mese chiuso il cui submit window e' aperto) |
| **Candidati reminder** | Dipendenti `FC > 60`, `EndWorkDate IS NULL`, `EmployerId = 2`, con `EmployeeAddress.WorkEmail` non NULL |
| **Esclusione** | Chi ha gia' `PathTracks SUBMITTED` per `DatePathTrack = mese_riferimento` (in proprio o come `InBehalfOfId`) |
| **Stage** | `opening` (giorno 1, info), `midway` (giorno 3, promemoria), `last-call` (giorno 5, urgente) |
| **Lingua email** | Default RO. Override con preferenza dipendente se disponibile (futuro). Per ora: RO |
| **Idempotenza** | File `state/reminders-{YYYY-MM-DD}-{stage}.done` impedisce doppio invio nello stesso giorno |
| **Close-month** | Eseguito il giorno 6 alle 02:00, scrive XLSX `state/missing-YYYY-MM.xlsx` di chi non ha ancora inviato. Niente email per ora — solo log + XLSX per HR |
| **BNR refresh** | Eseguito ogni giorno alle 09:00 (orario garantito post-pubblicazione BNR ~13:00). Pre-popola il tasso del giorno via `CurrencyService.resolve_for(today)` |

---

## File creati / modificati

**Creati:**
- `fdp_app/cli.py` — entry point CLI con sotto-comandi
- `fdp_app/notifications/__init__.py` (empty)
- `fdp_app/notifications/service.py` — `EmailReminderService`, `MonthCloser`, `BnrRefreshJob`
- `fdp_app/notifications/templates/email/reminder_opening_ro.txt`
- `fdp_app/notifications/templates/email/reminder_opening_it.txt`
- `fdp_app/notifications/templates/email/reminder_opening_en.txt`
- (idem `midway`, `last_call` → 9 file totali)
- `tests/test_cli.py`
- `tests/test_email_reminder_service.py`
- `tests/test_month_closer.py`
- `tests/test_bnr_refresh_job.py`
- `docs/install.md` — runbook deploy Waitress + IIS + Task Scheduler

**Modificati:**
- `fdp_app/repos/employee_repo.py` — nuovo metodo `find_pending_for_month`
- `requirements.txt` — niente di nuovo (tutto e' gia' presente)

---

## Task

### Fase A — Foundation CLI

#### Task 1: `fdp_app/cli.py` con scaffolding argparse

**File:** `fdp_app/cli.py`

```python
"""CLI entry point per task amministrativi e schedulati.

Uso:
    python -m fdp_app.cli send-reminders --stage=opening
    python -m fdp_app.cli close-month
    python -m fdp_app.cli refresh-bnr-rate
    python -m fdp_app.cli health-check

Eseguito da Windows Task Scheduler in produzione. Vedi docs/install.md.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from config.settings import Settings
from fdp_app import create_app
from fdp_app.db import Database


_BASE_DIR = Path(__file__).resolve().parent.parent

_logger = logging.getLogger("fdp.cli")


def _setup_logging() -> None:
    log_dir = _BASE_DIR / "logs"
    log_dir.mkdir(exist_ok=True)
    handler = logging.FileHandler(log_dir / "cli.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    _logger.addHandler(handler)
    _logger.addHandler(logging.StreamHandler(sys.stdout))
    _logger.setLevel(logging.INFO)


def _build_app():
    """Crea un'app Flask completa per condividere lo stesso config + db wrapper."""
    return create_app(settings=Settings, db=Database())


def cmd_send_reminders(args) -> int:
    from fdp_app.notifications.service import EmailReminderService
    app = _build_app()
    with app.app_context():
        svc = EmailReminderService(app)
        sent, skipped = svc.run_stage(args.stage)
    _logger.info("send-reminders %s: sent=%s, skipped=%s",
                  args.stage, sent, skipped)
    return 0


def cmd_close_month(args) -> int:
    from fdp_app.notifications.service import MonthCloser
    app = _build_app()
    with app.app_context():
        closer = MonthCloser(app)
        xlsx_path, count = closer.run()
    _logger.info("close-month: missing=%s xlsx=%s", count, xlsx_path)
    return 0


def cmd_refresh_bnr_rate(args) -> int:
    from fdp_app.notifications.service import BnrRefreshJob
    app = _build_app()
    with app.app_context():
        job = BnrRefreshJob(app)
        value, source = job.run()
    _logger.info("refresh-bnr-rate: value=%s source=%s", value, source)
    return 0


def cmd_health_check(args) -> int:
    """Quick connectivity + schema check."""
    app = _build_app()
    with app.app_context():
        from fdp_app.db import get_request_db
        try:
            conn = get_request_db()
            cur = conn.cursor()
            cur.execute("SELECT 1, COUNT(*) FROM Employee.fdp.PathTrackReimbursementRates")
            row = cur.fetchone()
            cur.close()
            _logger.info("health-check OK: db ping, rates_count=%s", row[1])
            return 0
        except Exception as e:
            _logger.error("health-check FAILED: %s", e)
            return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fdp", description="Fogli di Percorso CLI")
    sub = p.add_subparsers(dest="command", required=True)

    s1 = sub.add_parser("send-reminders", help="Invia email reminder per il mese precedente")
    s1.add_argument("--stage", choices=["opening", "midway", "last-call"], required=True)
    s1.set_defaults(func=cmd_send_reminders)

    s2 = sub.add_parser("close-month", help="Report XLSX dei mancanti dopo il 5")
    s2.set_defaults(func=cmd_close_month)

    s3 = sub.add_parser("refresh-bnr-rate", help="Pre-popola il tasso BNR del giorno")
    s3.set_defaults(func=cmd_refresh_bnr_rate)

    s4 = sub.add_parser("health-check", help="Verifica connettivita DB e schema")
    s4.set_defaults(func=cmd_health_check)

    return p


def main(argv=None) -> int:
    _setup_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as e:
        _logger.exception("Unhandled error in %s: %s", args.command, e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
```

**Test:** `tests/test_cli.py` con `argparse` test (parser smoke test, no DB).

Commit: `feat(cli): scaffold fdp.cli with 4 subcommands`

---

### Fase B — Email reminder

#### Task 2: `EmployeeRepo.find_pending_for_month`

**File:** `fdp_app/repos/employee_repo.py`

Aggiungere nuova query + metodo + dataclass `PendingEmployee`:

```python
_QUERY_PENDING = """
SELECT DISTINCT
    h.EmployeeHireHistoryId,
    e.EmployeeSurname,
    e.EmployeeName,
    ea.WorkEmail
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
    AND f.FunctionCode > ?
JOIN Employee.dbo.EmployeeAddress ea
     ON ea.EmployeeId = e.EmployeeId
    AND ea.DateOut IS NULL
    AND ea.WorkEmail IS NOT NULL
WHERE NOT EXISTS (
    SELECT 1 FROM Employee.fdp.PathTracks pt
    WHERE pt.DatePathTrack = ?
      AND pt.Status = 'SUBMITTED'
      AND pt.DateOut IS NULL
      AND (pt.EmployeeHireHistoryId = h.EmployeeHireHistoryId
           OR pt.InBehalfOfId = h.EmployeeHireHistoryId)
)
ORDER BY e.EmployeeSurname, e.EmployeeName
"""

@dataclass(frozen=True)
class PendingEmployee:
    employee_hire_history_id: int
    surname: str
    name: str
    work_email: str

    @property
    def full_name(self) -> str:
        return f"{self.surname} {self.name}"
```

E nel `EmployeeRepo`:

```python
def find_pending_for_month(self, *, date_path_track: date,
                            min_function_code: int = 60) -> list:
    cursor = self._open_cursor()
    try:
        cursor.execute(_QUERY_PENDING, min_function_code, date_path_track)
        rows = cursor.fetchall()
    finally:
        cursor.close()
    return [
        PendingEmployee(
            employee_hire_history_id=r[0],
            surname=r[1], name=r[2],
            work_email=r[3],
        )
        for r in rows
    ]
```

**Tests:** in `tests/test_employee_repo.py` aggiungi 3-4 test (no match, con match, query filter).

Commit: `feat(repos): EmployeeRepo.find_pending_for_month`

---

#### Task 3: Template email Jinja (9 file)

**Path:** `fdp_app/notifications/templates/email/`

Crea 9 file `.txt` (3 stage × 3 lingue). Esempio `reminder_opening_ro.txt`:

```
Subject: Fogli de drum - {{ month_name }} {{ year }}

Buna ziua {{ full_name }},

A inceput perioada de trimitere a fisei lunare pentru {{ month_name }} {{ year }}.

Te asteptam sa intri pe portalul intern si sa completezi declaratia ta:
  {{ app_url }}/pathtracks/new

Termenul ultim este data de 5 {{ next_month_name }} {{ next_year }} ora 23:59.

Multumesc,
Sistemul Fogli de drum
```

Esempio `reminder_last_call_ro.txt`:

```
Subject: URGENT - Ultima zi pentru fisa de {{ month_name }} {{ year }}

Buna ziua {{ full_name }},

ATENTIE: Astazi este ULTIMA ZI pentru a trimite fisa lunara
pentru {{ month_name }} {{ year }}.

Pana la ora 23:59 trebuie sa intri pe:
  {{ app_url }}/pathtracks/new

Dupa miezul noptii nu mai vei putea trimite.

Daca ai deja completat ciorna, asigura-te ca apesi "Confirma si trimite".

Multumesc,
Sistemul Fogli de drum
```

Stessa logica per IT e EN. Variabili disponibili nel template:
- `{{ full_name }}`, `{{ month_name }}`, `{{ year }}`,
  `{{ next_month_name }}`, `{{ next_year }}`, `{{ app_url }}`

Commit: `feat(notifications): email templates IT/RO/EN for 3 stages`

---

#### Task 4: `EmailReminderService`

**File:** `fdp_app/notifications/service.py`

```python
"""Servizi notifiche: reminder email, close-month report, BNR refresh."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Tuple

from dateutil.relativedelta import relativedelta
from jinja2 import Environment, FileSystemLoader, select_autoescape

from fdp_app.pathtracks.deadline import previous_month_first_day
from fdp_app.repos.employee_repo import EmployeeRepo
from email_connector import EmailSender

_logger = logging.getLogger("fdp.notifications")

_MONTH_NAMES = {
    "ro": ["", "Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie",
           "Iulie", "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie"],
    "it": ["", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
           "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"],
    "en": ["", "January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"],
}


class EmailReminderService:
    def __init__(self, app, default_lang: str = "ro") -> None:
        self._app = app
        self._default_lang = default_lang
        self._state_dir = Path(app.root_path).parent / "state"
        self._state_dir.mkdir(exist_ok=True)
        self._jinja = Environment(
            loader=FileSystemLoader(
                Path(app.root_path) / "notifications" / "templates" / "email"
            ),
            autoescape=False,  # plain-text emails
        )

    def _state_file(self, stage: str) -> Path:
        today = date.today().isoformat()
        return self._state_dir / f"reminders-{today}-{stage}.done"

    def _already_sent_today(self, stage: str) -> bool:
        return self._state_file(stage).exists()

    def _mark_sent(self, stage: str, summary: dict) -> None:
        self._state_file(stage).write_text(json.dumps(summary, indent=2),
                                            encoding="utf-8")

    def run_stage(self, stage: str) -> Tuple[int, int]:
        """Ritorna (sent, skipped)."""
        if stage not in ("opening", "midway", "last-call"):
            raise ValueError(f"stage non valido: {stage}")

        if self._already_sent_today(stage):
            _logger.info("Stage %s gia' inviato oggi, skip", stage)
            return 0, 0

        target_month = previous_month_first_day()
        target_year = target_month.year
        next_month = (target_month + relativedelta(months=1))

        db = self._app.config["_db"]
        repo = EmployeeRepo(db)
        pending = repo.find_pending_for_month(date_path_track=target_month)

        if not pending:
            _logger.info("Nessun dipendente pendente per %s", target_month)
            self._mark_sent(stage, {"sent": 0, "skipped": 0, "pending": 0})
            return 0, 0

        sender = EmailSender()
        sent_count = 0
        skipped_count = 0
        results = []

        lang = self._default_lang
        template_name = f"reminder_{stage.replace('-', '_')}_{lang}.txt"
        try:
            template = self._jinja.get_template(template_name)
        except Exception as e:
            _logger.error("Template %s non trovato: %s", template_name, e)
            raise

        for emp in pending:
            try:
                rendered = template.render(
                    full_name=emp.full_name,
                    month_name=_MONTH_NAMES[lang][target_month.month],
                    year=target_year,
                    next_month_name=_MONTH_NAMES[lang][next_month.month],
                    next_year=next_month.year,
                    app_url=self._app.config["_settings_cls"].APP_URL,
                )
                # Estrai Subject (prima riga "Subject: ...")
                lines = rendered.strip().split("\n")
                subject = lines[0].replace("Subject:", "").strip()
                body = "\n".join(lines[2:]).strip()
                sender.send_email(emp.work_email, subject, body, is_html=False)
                sent_count += 1
                results.append({"employee_id": emp.employee_hire_history_id,
                                 "email": emp.work_email, "status": "sent"})
                _logger.info("Reminder %s inviato a %s (%s)",
                              stage, emp.full_name, emp.work_email)
            except Exception as e:
                skipped_count += 1
                results.append({"employee_id": emp.employee_hire_history_id,
                                 "email": emp.work_email,
                                 "status": "error", "error": str(e)})
                _logger.error("Reminder %s fallito per %s: %s",
                                stage, emp.full_name, e)

        self._mark_sent(stage, {
            "sent": sent_count, "skipped": skipped_count,
            "pending": len(pending), "results": results,
        })
        return sent_count, skipped_count


class MonthCloser:
    """Genera XLSX dei pendenti dopo la scadenza del 5."""
    def __init__(self, app) -> None:
        self._app = app
        self._state_dir = Path(app.root_path).parent / "state"
        self._state_dir.mkdir(exist_ok=True)

    def run(self) -> Tuple[Path, int]:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill

        target_month = previous_month_first_day()
        db = self._app.config["_db"]
        repo = EmployeeRepo(db)
        pending = repo.find_pending_for_month(date_path_track=target_month)

        wb = Workbook()
        ws = wb.active
        ws.title = f"Mancanti {target_month:%Y-%m}"
        ws.append(["Cognome", "Nome", "Email"])
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="0B2A5B")
        for emp in pending:
            ws.append([emp.surname, emp.name, emp.work_email])
        for col in ws.columns:
            length = max(len(str(c.value or "")) for c in col)
            ws.column_dimensions[col[0].column_letter].width = min(length + 2, 50)

        out = self._state_dir / f"missing-{target_month:%Y-%m}.xlsx"
        wb.save(out)
        _logger.info("close-month: %s pendenti, file=%s", len(pending), out)
        return out, len(pending)


class BnrRefreshJob:
    """Pre-popola il tasso BNR del giorno corrente nella tabella."""
    def __init__(self, app) -> None:
        self._app = app

    def run(self) -> Tuple[float, str]:
        from fdp_app.pathtracks.currency import CurrencyService
        from fdp_app.pathtracks.bnr_client import BnrRateClient
        from fdp_app.repos.bnr_rate_repo import BnrRateRepo

        db = self._app.config["_db"]
        client = self._app.config.get("_bnr_client") or BnrRateClient()
        service = CurrencyService(bnr_repo=BnrRateRepo(db), bnr_client=client)
        resolved = service.resolve_for(date.today(), user_sys="bnr-refresh-job")
        _logger.info("BNR refresh: %s = %s", resolved.source, resolved.value_ron_per_eur)
        return resolved.value_ron_per_eur, resolved.source
```

**Tests:** 3 file separati con mock dei repos + EmailSender.

Commit: `feat(notifications): EmailReminderService + MonthCloser + BnrRefreshJob`

---

#### Task 5: Test CLI + servizi

3 file di test:
- `tests/test_cli.py` — argparse smoke + command dispatch
- `tests/test_email_reminder_service.py` — 7-8 test (stage validation, idempotenza, render template, skip se gia' inviato, multi-lingua placeholder)
- `tests/test_month_closer.py` — XLSX generato correttamente, schema
- `tests/test_bnr_refresh_job.py` — chiama CurrencyService, log

Commit: `test(notifications): coverage CLI + reminder + closer + bnr job`

---

### Fase C — Runbook deploy

#### Task 6: `docs/install.md`

**File:** `docs/install.md`

Sezione completa che documenta:
1. Prerequisiti server Windows (Python 3.11+, IIS, ODBC Driver 18 for SQL Server)
2. Installazione app (clone, venv, requirements, db_config.enc)
3. Migration SQL (001 + 002 + 004 in ordine)
4. Configurazione env vars (`FDP_SECRET_KEY`, `FDP_COOKIE_SECURE=1`, `FDP_APP_URL`)
5. Avvio Waitress dietro IIS (snippet web.config con `httpPlatformHandler`)
6. **4 Task Scheduler Windows**:
   - `fdp-reminder-opening` — giorno 1 alle 09:00 → `python -m fdp_app.cli send-reminders --stage=opening`
   - `fdp-reminder-midway` — giorno 3 alle 09:00 → idem `--stage=midway`
   - `fdp-reminder-last-call` — giorno 5 alle 09:00 → idem `--stage=last-call`
   - `fdp-close-month` — giorno 6 alle 02:00 → `python -m fdp_app.cli close-month`
   - `fdp-bnr-refresh` — ogni giorno alle 09:00 (working days) → `python -m fdp_app.cli refresh-bnr-rate`
7. Logs location, rotation, monitoring
8. Backup raccomandazioni

Esempio task scheduler XML/PowerShell incluso.

Commit: `docs: deployment runbook with Task Scheduler setup`

---

### Fase D — Smoke + tag

#### Task 7: Smoke test + tag `v0.6.0-notifications`

1. Eseguire suite completa: `pytest -q` (target ~270 test).
2. Smoke test CLI manuale:
   - `python -m fdp_app.cli health-check` → OK
   - `python -m fdp_app.cli refresh-bnr-rate` → fetch + insert in BnrRates
   - `python -m fdp_app.cli send-reminders --stage=opening` (in ambiente staging con email di test) → email arriva, `state/reminders-YYYY-MM-DD-opening.done` creato
   - `python -m fdp_app.cli close-month` → `state/missing-YYYY-MM.xlsx` generato
3. Tag:
   ```bash
   git tag -a v0.6.0-notifications -m "Piano 6 - Notifiche & scheduler"
   git push origin main
   git push origin v0.6.0-notifications
   ```

---

## Definition of Done

- [x] CLI `python -m fdp_app.cli` con 4 sotto-comandi
- [x] `EmployeeRepo.find_pending_for_month` con query EXISTS-NOT-EXISTS
- [x] 9 template email Jinja (3 stage × 3 lingue)
- [x] `EmailReminderService` con idempotenza file di stato
- [x] `MonthCloser` con XLSX
- [x] `BnrRefreshJob` che chiama `CurrencyService`
- [x] `docs/install.md` con runbook Task Scheduler
- [x] Tutti i test verdi (~270 target)
- [x] Tag `v0.6.0-notifications`

## Prossimo passo

Con il Piano 6 il sistema e' **FUNZIONALMENTE COMPLETO** secondo lo spec
originale. Possibili evoluzioni post-MVP:
- Piano 7 — Audit polish (P3 + dark mode opzionale + UX delight)
- Piano 8 — Mobile responsive deep-dive
- Piano 9 — Reporting analytics (dashboard manager)
