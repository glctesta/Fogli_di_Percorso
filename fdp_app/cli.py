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

_BASE_DIR = Path(__file__).resolve().parent.parent
_logger = logging.getLogger("fdp.cli")


def _setup_logging() -> None:
    log_dir = _BASE_DIR / "logs"
    log_dir.mkdir(exist_ok=True)
    handler = logging.FileHandler(log_dir / "cli.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    if not _logger.handlers:
        _logger.addHandler(handler)
        _logger.addHandler(logging.StreamHandler(sys.stdout))
    _logger.setLevel(logging.INFO)


def _build_app():
    """Crea un'app Flask completa per condividere lo stesso config + db wrapper."""
    from config.settings import Settings
    from fdp_app import create_app
    from fdp_app.db import Database
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

    s1 = sub.add_parser("send-reminders",
                         help="Invia email reminder per il mese precedente")
    s1.add_argument("--stage", choices=["opening", "midway", "last-call"],
                     required=True)
    s1.set_defaults(func=cmd_send_reminders)

    s2 = sub.add_parser("close-month",
                         help="Report XLSX dei mancanti dopo il 5")
    s2.set_defaults(func=cmd_close_month)

    s3 = sub.add_parser("refresh-bnr-rate",
                         help="Pre-popola il tasso BNR del giorno")
    s3.set_defaults(func=cmd_refresh_bnr_rate)

    s4 = sub.add_parser("health-check",
                         help="Verifica connettivita DB e schema")
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
