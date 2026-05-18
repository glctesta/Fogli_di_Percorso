"""Logica di business per la gestione del punto di partenza."""
from __future__ import annotations

from typing import Optional

from fdp_app.pathtracks.routing import RoutingClient
from fdp_app.repos.coordinate_repo import ActiveCoordinate, CoordinateRepo


class ActiveCoordinateAlreadyExists(Exception):
    """Raised quando si tenta di inserire un punto mentre ne esiste gia'
    uno attivo (DateOut IS NULL) per lo stesso dipendente."""


class CoordinateService:
    """Orchestrazione: routing + repo. Single-responsibility per gestione punto."""

    def __init__(
        self,
        repo: CoordinateRepo,
        routing: RoutingClient,
        workplace: dict,
    ) -> None:
        self._repo = repo
        self._routing = routing
        self._workplace = workplace

    def find_active(self, employee_hire_history_id: int) -> Optional[ActiveCoordinate]:
        return self._repo.find_active(employee_hire_history_id)

    def create(
        self,
        *,
        employee_hire_history_id: int,
        label: str,
        lat: float,
        lon: float,
    ) -> int:
        existing = self._repo.find_active(employee_hire_history_id)
        if existing is not None:
            raise ActiveCoordinateAlreadyExists(
                f"Il dipendente {employee_hire_history_id} ha gia' un punto attivo "
                f"(id={existing.coordinate_id}). Cancellarlo prima di crearne uno nuovo."
            )

        road_km = self._routing.road_km(
            start=(lat, lon),
            end=(self._workplace["lat"], self._workplace["lon"]),
        )
        return self._repo.insert(
            employee_hire_history_id=employee_hire_history_id,
            label=label,
            lat=lat,
            lon=lon,
            road_km_to_workplace=road_km,
        )

    def delete(
        self, *, coordinate_id: int, employee_hire_history_id: int
    ) -> bool:
        return self._repo.soft_delete(
            coordinate_id=coordinate_id,
            employee_hire_history_id=employee_hire_history_id,
        )
