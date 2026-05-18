"""Client per il calcolo della distanza stradale (OSRM primario, ORS fallback).

Usa OSRM pubblico se disponibile; in caso di errore, prova ORS se la
API key e' configurata. Cache in-process per coppia (lat,lon) -> km.

Note di formato:
- OSRM: coordinate in ordine lon,lat nell'URL; distance in metri.
- ORS: coordinate sempre lon,lat; distance in metri.
- Nominatim: lat e lon come query string separati.

Nota cache: l'utente puo' avere un solo punto di partenza attivo, quindi
la cache contiene tipicamente 1-2 entry per processo. Non serve eviction.
"""
from __future__ import annotations

from threading import Lock
from typing import Optional, Tuple

import requests

OSRM_PATH = "/route/v1/driving/"
ORS_PATH = "/v2/directions/driving-car"

LatLon = Tuple[float, float]


class RoutingError(Exception):
    """Raised quando nessun provider riesce a calcolare la rotta."""


class RoutingClient:
    def __init__(
        self,
        osrm_base: str,
        ors_base: str,
        ors_api_key: Optional[str],
        timeout_s: float = 6.0,
    ) -> None:
        self._osrm_base = osrm_base.rstrip("/")
        self._ors_base = ors_base.rstrip("/")
        self._ors_api_key = ors_api_key
        self._timeout = timeout_s
        self._cache: dict[Tuple[LatLon, LatLon], float] = {}
        self._lock = Lock()

    def road_km(self, *, start: LatLon, end: LatLon) -> float:
        """Ritorna distanza stradale in km. Tenta OSRM, poi ORS.

        Raises RoutingError se nessuno dei due risponde correttamente.
        """
        key = (start, end)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                return cached

        km = self._try_osrm(start, end)
        if km is None:
            km = self._try_ors(start, end)
        if km is None:
            raise RoutingError(
                f"Nessun provider ha calcolato la rotta {start} -> {end}"
            )

        with self._lock:
            self._cache[key] = km
        return km

    def _try_osrm(self, start: LatLon, end: LatLon) -> Optional[float]:
        # OSRM richiede lon,lat nell'URL
        url = (
            f"{self._osrm_base}{OSRM_PATH}"
            f"{start[1]},{start[0]};{end[1]},{end[0]}"
        )
        try:
            resp = requests.get(url, params={"overview": "false"}, timeout=self._timeout)
        except requests.RequestException:
            return None
        if resp.status_code != 200:
            return None
        try:
            data = resp.json()
        except ValueError:
            return None
        if data.get("code") != "Ok":
            return None
        routes = data.get("routes") or []
        if not routes:
            return None
        meters = routes[0].get("distance")
        if not isinstance(meters, (int, float)):
            return None
        return float(meters) / 1000.0

    def _try_ors(self, start: LatLon, end: LatLon) -> Optional[float]:
        if not self._ors_api_key:
            return None
        url = f"{self._ors_base}{ORS_PATH}"
        params = {
            "api_key": self._ors_api_key,
            "start": f"{start[1]},{start[0]}",
            "end": f"{end[1]},{end[0]}",
        }
        try:
            resp = requests.get(url, params=params, timeout=self._timeout)
        except requests.RequestException:
            return None
        if resp.status_code != 200:
            return None
        try:
            data = resp.json()
        except ValueError:
            return None
        features = data.get("features") or []
        if not features:
            return None
        summary = features[0].get("properties", {}).get("summary", {})
        meters = summary.get("distance")
        if not isinstance(meters, (int, float)):
            return None
        return float(meters) / 1000.0
