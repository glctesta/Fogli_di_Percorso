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


def can_create_draft_for(date_path_track: date) -> bool:
    """True se l'utente puo' creare o modificare una bozza per quel mese.

    Mese ammesso:
    - corrente (sempre)
    - precedente (solo fino al 5 del mese corrente)
    Mesi futuri o piu' vecchi di 2 mesi: vietato.
    """
    today = datetime.now(_TZ).date()
    current_month = today.replace(day=1)

    if date_path_track == current_month:
        return True

    previous_month = current_month - relativedelta(months=1)
    if date_path_track == previous_month:
        deadline_day = current_month.replace(day=5)
        return today <= deadline_day

    return False


def can_submit_for(date_path_track: date) -> bool:
    """True se l'utente puo' inviare (submit) una bozza per quel mese.

    Alias di is_open_for_month: finestra 1-5 del mese successivo a date_path_track.
    """
    return is_open_for_month(date_path_track)
