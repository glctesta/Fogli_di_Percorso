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
    next_month_first = (date_path_track + relativedelta(months=1)).replace(day=1)
    window_open = datetime.combine(next_month_first, time(0, 0, 0), tzinfo=_TZ)
    window_close = datetime.combine(
        next_month_first.replace(day=5), time(23, 59, 59), tzinfo=_TZ
    )
    return window_open <= now <= window_close
