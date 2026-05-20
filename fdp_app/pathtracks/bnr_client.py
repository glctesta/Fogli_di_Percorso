"""Client per il tasso di cambio EUR-RON.

Strategia:
1. Live fetch da BNR.ro (XML)
2. Fallback su cursbnr.ro (JSON pubblico)

Solleva BnrRateUnavailable se entrambi falliscono.
"""
from __future__ import annotations

from typing import Optional

import defusedxml.ElementTree as ET
import requests


BNR_XML_URL = "https://www.bnr.ro/nbrfxrates.xml"
CURSBNR_API_URL = "https://www.cursbnr.ro/api/curs.json"


class BnrRateUnavailable(Exception):
    """Nessun provider e' riuscito a ottenere il tasso EUR->RON."""


class BnrRateClient:
    def __init__(self, *, timeout_s: float = 6.0) -> None:
        self._timeout = timeout_s

    def fetch_eur_to_ron(self) -> tuple[float, str]:
        """Ritorna (rate_value, source) dove source = 'BNR' o 'CURSBNR'.

        Raises BnrRateUnavailable se entrambi falliscono.
        """
        rate = self._try_bnr()
        if rate is not None:
            return rate, "BNR"
        rate = self._try_cursbnr()
        if rate is not None:
            return rate, "CURSBNR"
        raise BnrRateUnavailable(
            "Tasso EUR-RON non disponibile (BNR e cursbnr falliti)"
        )

    def _try_bnr(self) -> Optional[float]:
        try:
            resp = requests.get(BNR_XML_URL, timeout=self._timeout)
        except requests.RequestException:
            return None
        if resp.status_code != 200:
            return None
        try:
            root = ET.fromstring(resp.content)
        except Exception:
            return None
        # Iter through all elements to find Rate elements with currency="EUR"
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "Rate" and elem.get("currency") == "EUR":
                try:
                    multiplier = float(elem.get("multiplier", "1") or 1)
                    val = float((elem.text or "").replace(",", "."))
                    return val / multiplier
                except (ValueError, TypeError):
                    return None
        return None

    def _try_cursbnr(self) -> Optional[float]:
        try:
            resp = requests.get(CURSBNR_API_URL, timeout=self._timeout)
        except requests.RequestException:
            return None
        if resp.status_code != 200:
            return None
        try:
            data = resp.json()
        except ValueError:
            return None
        # Two common shapes: {"rates": {"EUR": ...}} or {"EUR": ...}
        if isinstance(data, dict):
            rates = data.get("rates")
            if isinstance(rates, dict) and "EUR" in rates:
                try:
                    return float(rates["EUR"])
                except (ValueError, TypeError):
                    return None
            if "EUR" in data:
                try:
                    return float(data["EUR"])
                except (ValueError, TypeError):
                    return None
        return None
