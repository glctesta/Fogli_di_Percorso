"""Test CLI parser smoke."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from fdp_app.cli import build_parser, main


def test_parser_send_reminders_requires_stage():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["send-reminders"])


def test_parser_send_reminders_with_stage():
    parser = build_parser()
    args = parser.parse_args(["send-reminders", "--stage=opening"])
    assert args.command == "send-reminders"
    assert args.stage == "opening"


def test_parser_send_reminders_rejects_invalid_stage():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["send-reminders", "--stage=invalid"])


def test_parser_close_month():
    parser = build_parser()
    args = parser.parse_args(["close-month"])
    assert args.command == "close-month"


def test_parser_refresh_bnr_rate():
    parser = build_parser()
    args = parser.parse_args(["refresh-bnr-rate"])
    assert args.command == "refresh-bnr-rate"


def test_parser_health_check():
    parser = build_parser()
    args = parser.parse_args(["health-check"])
    assert args.command == "health-check"


def test_parser_requires_subcommand():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_rejects_unknown_command():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["unknown-command"])


# --- Dispatch tests: main() routes to the right service class. -------------
# The CLI functions lazily import services and call _build_app(); we stub
# both so no real Flask app / DB / network is involved.


def _stub_build_app(monkeypatch):
    """Replace cli._build_app with a no-DB Flask app that supports app_context."""
    from flask import Flask
    import fdp_app.cli as cli_mod

    app = Flask(__name__)
    app.config["_db"] = MagicMock()
    monkeypatch.setattr(cli_mod, "_build_app", lambda: app)
    return app


def test_main_send_reminders_invokes_run_stage_with_opening(monkeypatch):
    _stub_build_app(monkeypatch)

    svc_instance = MagicMock()
    svc_instance.run_stage.return_value = (3, 0)
    svc_cls = MagicMock(return_value=svc_instance)
    monkeypatch.setattr(
        "fdp_app.notifications.service.EmailReminderService", svc_cls,
    )

    rc = main(["send-reminders", "--stage=opening"])

    assert rc == 0
    svc_instance.run_stage.assert_called_once_with("opening")


def test_main_close_month_invokes_month_closer_run(monkeypatch):
    _stub_build_app(monkeypatch)

    closer = MagicMock()
    closer.run.return_value = ("dummy/path.xlsx", 0)
    closer_cls = MagicMock(return_value=closer)
    monkeypatch.setattr(
        "fdp_app.notifications.service.MonthCloser", closer_cls,
    )

    rc = main(["close-month"])

    assert rc == 0
    closer.run.assert_called_once_with()


def test_main_refresh_bnr_rate_invokes_bnr_refresh_job_run(monkeypatch):
    _stub_build_app(monkeypatch)

    job = MagicMock()
    job.run.return_value = (4.97, "BNR")
    job_cls = MagicMock(return_value=job)
    monkeypatch.setattr(
        "fdp_app.notifications.service.BnrRefreshJob", job_cls,
    )

    rc = main(["refresh-bnr-rate"])

    assert rc == 0
    job.run.assert_called_once_with()
