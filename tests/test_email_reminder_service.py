"""Test del EmailReminderService.

Coverage:
- Validazione stage
- Idempotenza tramite file .done in state/
- Branch nessun pendente
- Happy path con 2 destinatari
- Fallimento per-employee non interrompe il batch
- Template mancante / malformato
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from flask import Flask
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from fdp_app.notifications.service import EmailReminderService
from fdp_app.repos.employee_repo import PendingEmployee


# Real templates dir of the project; we always copy/use these so the loader
# resolves real reminder_<stage>_<lang>.txt files.
_REAL_TPL_DIR = (
    Path(__file__).resolve().parent.parent
    / "fdp_app" / "notifications" / "templates" / "email"
)


def _make_flask_app(tmp_path: Path) -> Flask:
    """Crea un Flask con root_path su tmp_path e templates copiati."""
    root = tmp_path / "fdp_app"
    root.mkdir(parents=True, exist_ok=True)
    tpl_dir = root / "notifications" / "templates" / "email"
    tpl_dir.mkdir(parents=True, exist_ok=True)
    # Copy real templates so service finds them.
    for src in _REAL_TPL_DIR.glob("*.txt"):
        (tpl_dir / src.name).write_text(
            src.read_text(encoding="utf-8"), encoding="utf-8"
        )

    app = Flask(__name__, root_path=str(root))
    app.config["_db"] = MagicMock()

    class FakeSettings:
        APP_URL = "http://test.local"

    app.config["_settings_cls"] = FakeSettings
    return app


def _patch_repo_pending(monkeypatch, pending_list):
    """Patches EmployeeRepo.find_pending_for_month inside the service module."""
    import fdp_app.notifications.service as svc_mod

    fake_repo_cls = MagicMock()
    fake_repo = MagicMock()
    fake_repo.find_pending_for_month.return_value = pending_list
    fake_repo_cls.return_value = fake_repo
    monkeypatch.setattr(svc_mod, "EmployeeRepo", fake_repo_cls)
    return fake_repo


def test_run_stage_rejects_invalid_stage(tmp_path):
    app = _make_flask_app(tmp_path)
    svc = EmailReminderService(app)
    with pytest.raises(ValueError, match="stage non valido"):
        svc.run_stage("not-a-stage")


def test_run_stage_skips_when_already_sent_today(tmp_path, monkeypatch):
    app = _make_flask_app(tmp_path)
    sender = MagicMock()
    svc = EmailReminderService(app, email_sender=sender)
    # Pre-create the .done file for today.
    today = date.today().isoformat()
    (svc._state_dir / f"reminders-{today}-opening.done").write_text(
        '{"sent":1,"skipped":0,"pending":1}', encoding="utf-8"
    )
    # If repo is called, fail loudly.
    _patch_repo_pending(monkeypatch, ["should-not-be-touched"])

    result = svc.run_stage("opening")

    assert result == (0, 0)
    sender.send_email.assert_not_called()


def test_run_stage_writes_done_file_when_no_pending(tmp_path, monkeypatch):
    app = _make_flask_app(tmp_path)
    sender = MagicMock()
    svc = EmailReminderService(app, email_sender=sender)
    _patch_repo_pending(monkeypatch, [])

    sent, skipped = svc.run_stage("opening")

    assert (sent, skipped) == (0, 0)
    today = date.today().isoformat()
    done = svc._state_dir / f"reminders-{today}-opening.done"
    assert done.exists()
    summary = json.loads(done.read_text(encoding="utf-8"))
    assert summary == {"sent": 0, "skipped": 0, "pending": 0}
    sender.send_email.assert_not_called()


def test_run_stage_sends_email_per_pending_employee(tmp_path, monkeypatch):
    app = _make_flask_app(tmp_path)
    sender = MagicMock()
    svc = EmailReminderService(app, email_sender=sender)
    pending = [
        PendingEmployee(
            employee_hire_history_id=101,
            surname="Bianchi",
            name="Luigi",
            work_email="lbianchi@example.com",
        ),
        PendingEmployee(
            employee_hire_history_id=102,
            surname="Verdi",
            name="Maria",
            work_email="mverdi@example.com",
        ),
    ]
    _patch_repo_pending(monkeypatch, pending)

    sent, skipped = svc.run_stage("opening")

    assert (sent, skipped) == (2, 0)
    assert sender.send_email.call_count == 2
    # Verify call signature: (to, subject, body, is_html=False)
    first_call = sender.send_email.call_args_list[0]
    to_email, subject, body = first_call.args[0:3]
    assert to_email == "lbianchi@example.com"
    assert subject  # non-empty
    assert "Subject:" not in body  # body shouldn't contain the header
    assert first_call.kwargs.get("is_html") is False

    today = date.today().isoformat()
    done = svc._state_dir / f"reminders-{today}-opening.done"
    assert done.exists()
    summary = json.loads(done.read_text(encoding="utf-8"))
    assert summary["sent"] == 2
    assert summary["skipped"] == 0
    assert summary["pending"] == 2
    assert len(summary["results"]) == 2
    assert all(r["status"] == "sent" for r in summary["results"])


def test_run_stage_continues_on_per_employee_failure(tmp_path, monkeypatch):
    app = _make_flask_app(tmp_path)
    sender = MagicMock()
    # First call raises, second succeeds.
    sender.send_email.side_effect = [
        RuntimeError("SMTP boom"),
        None,
    ]
    svc = EmailReminderService(app, email_sender=sender)
    pending = [
        PendingEmployee(101, "Bianchi", "Luigi", "lbianchi@example.com"),
        PendingEmployee(102, "Verdi", "Maria", "mverdi@example.com"),
    ]
    _patch_repo_pending(monkeypatch, pending)

    sent, skipped = svc.run_stage("opening")

    assert sent == 1
    assert skipped == 1
    assert sender.send_email.call_count == 2

    today = date.today().isoformat()
    done = svc._state_dir / f"reminders-{today}-opening.done"
    summary = json.loads(done.read_text(encoding="utf-8"))
    assert summary["sent"] == 1
    assert summary["skipped"] == 1
    assert summary["pending"] == 2
    statuses = [r["status"] for r in summary["results"]]
    assert "sent" in statuses and "error" in statuses
    error_record = next(r for r in summary["results"] if r["status"] == "error")
    assert "RuntimeError" in error_record["error"]


def test_run_stage_template_not_found_propagates(tmp_path, monkeypatch):
    """If the required template file is missing, TemplateError propagates."""
    app = _make_flask_app(tmp_path)
    # Replace _jinja with an env pointing at an empty tmp dir.
    empty_dir = tmp_path / "empty_templates"
    empty_dir.mkdir()
    svc = EmailReminderService(app, email_sender=MagicMock())
    svc._jinja = Environment(loader=FileSystemLoader(str(empty_dir)),
                              autoescape=False)
    # Non-empty pending list, otherwise template is never loaded.
    pending = [PendingEmployee(1, "Rossi", "Mario", "mr@example.com")]
    _patch_repo_pending(monkeypatch, pending)

    with pytest.raises(TemplateNotFound):
        svc.run_stage("opening")


def test_run_stage_template_without_subject_header_raises_value_error(
    tmp_path, monkeypatch,
):
    """Body without 'Subject:' prefix -> ValueError mentioning template name."""
    app = _make_flask_app(tmp_path)
    # Replace _jinja to point at a dir with a malformed template.
    bad_dir = tmp_path / "bad_templates"
    bad_dir.mkdir()
    # Template lacks the Subject: prefix on header.
    (bad_dir / "reminder_opening_ro.txt").write_text(
        "Salutare {{ full_name }}\n\nCorpo del messaggio.\n",
        encoding="utf-8",
    )
    svc = EmailReminderService(app, email_sender=MagicMock())
    svc._jinja = Environment(loader=FileSystemLoader(str(bad_dir)),
                              autoescape=False)
    pending = [PendingEmployee(1, "Rossi", "Mario", "mr@example.com")]
    _patch_repo_pending(monkeypatch, pending)

    # Bad-subject error is caught per-employee and recorded as skipped.
    sent, skipped = svc.run_stage("opening")

    assert sent == 0
    assert skipped == 1
    today = date.today().isoformat()
    done = svc._state_dir / f"reminders-{today}-opening.done"
    summary = json.loads(done.read_text(encoding="utf-8"))
    err = summary["results"][0]["error"]
    assert "ValueError" in err
    assert "reminder_opening_ro.txt" in err


def test_run_stage_preserves_blank_lines_inside_body(tmp_path, monkeypatch):
    """Body containing multiple blank lines should be preserved after the
    Subject header is partitioned away."""
    app = _make_flask_app(tmp_path)
    custom_dir = tmp_path / "custom_templates"
    custom_dir.mkdir()
    # Template with multi-paragraph body separated by blank lines.
    (custom_dir / "reminder_opening_ro.txt").write_text(
        "Subject: Test {{ full_name }}\n"
        "\n"
        "Paragraph one.\n"
        "\n"
        "Paragraph two.\n"
        "\n"
        "Paragraph three.\n",
        encoding="utf-8",
    )
    sender = MagicMock()
    svc = EmailReminderService(app, email_sender=sender)
    svc._jinja = Environment(loader=FileSystemLoader(str(custom_dir)),
                              autoescape=False)
    pending = [PendingEmployee(1, "Rossi", "Mario", "mr@example.com")]
    _patch_repo_pending(monkeypatch, pending)

    sent, skipped = svc.run_stage("opening")

    assert (sent, skipped) == (1, 0)
    call = sender.send_email.call_args_list[0]
    to_email, subject, body = call.args[0:3]
    assert subject == "Test Rossi Mario"
    # Body keeps internal blank lines between paragraphs.
    assert "Paragraph one." in body
    assert "Paragraph two." in body
    assert "Paragraph three." in body
    # The blank lines between paragraphs must be preserved.
    assert "Paragraph one.\n\nParagraph two." in body
