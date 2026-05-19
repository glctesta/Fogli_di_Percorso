"""Test della finestra di scadenza (entro il 5 del mese successivo)."""
from __future__ import annotations

from datetime import date

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
    with freeze_time("2026-05-01 00:00:00+02:00"):  # Europe/Rome (CEST)
        assert is_open_for_month(date(2026, 4, 1)) is True


def test_window_open_fifth_day_late():
    with freeze_time("2026-05-05 23:59:59+02:00"):
        assert is_open_for_month(date(2026, 4, 1)) is True


def test_window_closed_sixth_day():
    with freeze_time("2026-05-06 00:00:00+02:00"):
        assert is_open_for_month(date(2026, 4, 1)) is False


def test_window_closed_before_period():
    with freeze_time("2026-04-15 10:00:00+02:00"):
        assert is_open_for_month(date(2026, 4, 1)) is False


def test_window_closed_for_older_month():
    with freeze_time("2026-05-15 10:00:00+02:00"):
        assert is_open_for_month(date(2026, 3, 1)) is False


def test_window_open_for_december_in_january():
    with freeze_time("2026-01-05 23:59:59+01:00"):  # CET
        assert is_open_for_month(date(2025, 12, 1)) is True


# --- Tests for can_create_draft_for ---

from fdp_app.pathtracks.deadline import can_create_draft_for, can_submit_for


def test_can_create_draft_for_current_month():
    """Bozza per il mese corrente sempre permessa."""
    with freeze_time("2026-05-15 10:00:00+02:00"):
        assert can_create_draft_for(date(2026, 5, 1)) is True


def test_can_create_draft_for_current_month_on_first_day():
    with freeze_time("2026-05-01 00:00:00+02:00"):
        assert can_create_draft_for(date(2026, 5, 1)) is True


def test_can_create_draft_for_current_month_on_last_day():
    with freeze_time("2026-05-31 23:59:59+02:00"):
        assert can_create_draft_for(date(2026, 5, 1)) is True


def test_can_create_draft_for_previous_month_within_deadline():
    """Bozza per mese precedente OK fino al giorno 5 del corrente."""
    with freeze_time("2026-05-03 10:00:00+02:00"):
        assert can_create_draft_for(date(2026, 4, 1)) is True


def test_can_create_draft_for_previous_month_on_deadline_day():
    with freeze_time("2026-05-05 23:59:59+02:00"):
        assert can_create_draft_for(date(2026, 4, 1)) is True


def test_can_create_draft_for_previous_month_after_deadline():
    """Bozza per mese precedente bloccata dal giorno 6."""
    with freeze_time("2026-05-06 00:00:00+02:00"):
        assert can_create_draft_for(date(2026, 4, 1)) is False


def test_cannot_create_draft_for_future_month():
    with freeze_time("2026-05-15 10:00:00+02:00"):
        assert can_create_draft_for(date(2026, 6, 1)) is False


def test_cannot_create_draft_for_two_months_ago():
    with freeze_time("2026-05-15 10:00:00+02:00"):
        assert can_create_draft_for(date(2026, 3, 1)) is False


def test_cannot_create_draft_for_very_old_month():
    with freeze_time("2026-05-15 10:00:00+02:00"):
        assert can_create_draft_for(date(2025, 12, 1)) is False


# --- Tests for can_submit_for (alias of is_open_for_month) ---

def test_can_submit_for_in_window():
    with freeze_time("2026-05-03 10:00:00+02:00"):
        assert can_submit_for(date(2026, 4, 1)) is True


def test_can_submit_for_outside_window():
    with freeze_time("2026-05-15 10:00:00+02:00"):
        assert can_submit_for(date(2026, 4, 1)) is False


def test_can_submit_for_current_month_returns_false_in_same_month():
    """Non si puo' inviare la dichiarazione del mese corrente durante lo stesso mese."""
    with freeze_time("2026-05-15 10:00:00+02:00"):
        # Submit per maggio si puo' fare solo dal 1 al 5 giugno
        assert can_submit_for(date(2026, 5, 1)) is False
