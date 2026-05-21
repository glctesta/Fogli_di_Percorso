"""Test CLI parser smoke."""
from __future__ import annotations

import pytest

from fdp_app.cli import build_parser


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
