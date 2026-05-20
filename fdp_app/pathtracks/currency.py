"""Lookup tasso EUR->RON con cascata:
1. Tasso amministrativo (IsStandard=1, ValidFrom..ValidTo)
2. Live fetch (BNR -> cursbnr)
3. Ultimo tasso cached (stale, con warning)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from fdp_app.pathtracks.bnr_client import BnrRateClient, BnrRateUnavailable
from fdp_app.repos.bnr_rate_repo import BnrRateRepo


class RateNotResolvableError(Exception):
    """Nessuna delle 3 strategie (standard, live, cached) ha trovato un tasso."""


@dataclass(frozen=True)
class ResolvedRate:
    value_ron_per_eur: float
    source: str  # 'STANDARD' | 'BNR' | 'CURSBNR'
    stale: bool  # True quando il tasso e' cached (potenzialmente vecchio)


class CurrencyService:
    def __init__(self, *, bnr_repo: BnrRateRepo, bnr_client: BnrRateClient) -> None:
        self._repo = bnr_repo
        self._client = bnr_client

    def resolve_for(self, target_date: date, *, user_sys: str) -> ResolvedRate:
        # 1) Standard amministrativo (range valido)
        std = self._repo.find_standard_for(target_date)
        if std is not None:
            return ResolvedRate(
                value_ron_per_eur=std.rate_value_ron_per_eur,
                source="STANDARD",
                stale=False,
            )

        # 2) Live fetch BNR -> cursbnr
        try:
            value, source = self._client.fetch_eur_to_ron()
            # Persiste per uso futuro / audit
            self._repo.insert(
                rate_value_ron_per_eur=value,
                source=source,
                valid_from=target_date,
                valid_to=None,
                is_standard=False,
                user_sys=user_sys,
            )
            return ResolvedRate(
                value_ron_per_eur=value, source=source, stale=False,
            )
        except BnrRateUnavailable:
            pass

        # 3) Ultimo cached
        cached = self._repo.find_latest_cached_for(target_date)
        if cached is not None:
            return ResolvedRate(
                value_ron_per_eur=cached.rate_value_ron_per_eur,
                source=cached.source,
                stale=True,
            )

        raise RateNotResolvableError(
            f"Nessun tasso EUR->RON disponibile per {target_date}"
        )
