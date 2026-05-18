"""Test del CoordinateService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from fdp_app.coordinates.service import (
    CoordinateService,
    ActiveCoordinateAlreadyExists,
)
from fdp_app.pathtracks.routing import RoutingError
from fdp_app.repos.coordinate_repo import ActiveCoordinate


def _service(repo=None, routing=None, workplace=None):
    repo = repo or MagicMock()
    routing = routing or MagicMock()
    workplace = workplace or {"lat": 50.0, "lon": 3.0}
    return CoordinateService(repo=repo, routing=routing, workplace=workplace), repo, routing


def test_find_active_delegates_to_repo():
    expected = ActiveCoordinate(1, "x", 45.0, 9.0, 12.5)
    svc, repo, _ = _service()
    repo.find_active.return_value = expected

    result = svc.find_active(employee_hire_history_id=42)

    assert result is expected
    repo.find_active.assert_called_once_with(42)


def test_create_when_no_active_calls_routing_and_inserts():
    svc, repo, routing = _service(workplace={"lat": 50.5, "lon": 3.3})
    repo.find_active.return_value = None
    routing.road_km.return_value = 12.345
    repo.insert.return_value = 200

    new_id = svc.create(
        employee_hire_history_id=42, label="Casa", lat=45.0, lon=9.0
    )

    assert new_id == 200
    routing.road_km.assert_called_once_with(
        start=(45.0, 9.0), end=(50.5, 3.3)
    )
    repo.insert.assert_called_once_with(
        employee_hire_history_id=42,
        label="Casa",
        lat=45.0,
        lon=9.0,
        road_km_to_workplace=12.345,
    )


def test_create_when_active_exists_raises():
    svc, repo, _ = _service()
    repo.find_active.return_value = ActiveCoordinate(1, "old", 1, 2, 3)

    with pytest.raises(ActiveCoordinateAlreadyExists):
        svc.create(employee_hire_history_id=42, label="x", lat=1.0, lon=2.0)

    repo.insert.assert_not_called()


def test_create_propagates_routing_error():
    svc, repo, routing = _service()
    repo.find_active.return_value = None
    routing.road_km.side_effect = RoutingError("OSRM down")

    with pytest.raises(RoutingError):
        svc.create(employee_hire_history_id=42, label="x", lat=1.0, lon=2.0)

    repo.insert.assert_not_called()


def test_delete_delegates_to_repo():
    svc, repo, _ = _service()
    repo.soft_delete.return_value = True

    result = svc.delete(coordinate_id=100, employee_hire_history_id=42)

    assert result is True
    repo.soft_delete.assert_called_once_with(
        coordinate_id=100, employee_hire_history_id=42
    )
