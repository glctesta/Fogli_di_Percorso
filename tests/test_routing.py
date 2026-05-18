"""Test del client di routing OSRM + fallback ORS."""
from __future__ import annotations

import pytest
import responses
from responses import matchers

from fdp_app.pathtracks.routing import (
    RoutingClient,
    RoutingError,
    OSRM_PATH,
)


OSRM_BASE = "https://router.project-osrm.org"
ORS_BASE = "https://api.openrouteservice.org"

# NOTA: Python `float` strips trailing zeros nel format string,
# quindi (45.50, 9.20) viene formattato come "45.5,9.2" nell'URL.
# I mock devono usare i valori effettivamente prodotti dal client.
OSRM_URL = f"{OSRM_BASE}{OSRM_PATH}9.19,45.4642;9.2,45.5"
ORS_URL = f"{ORS_BASE}/v2/directions/driving-car"


@pytest.fixture
def mocked_responses():
    with responses.RequestsMock() as rsps:
        yield rsps


def test_osrm_returns_road_km_on_success(mocked_responses):
    mocked_responses.get(
        OSRM_URL,
        json={
            "code": "Ok",
            "routes": [{"distance": 5300.5, "duration": 600}],
        },
        status=200,
        match=[matchers.query_param_matcher({"overview": "false"})],
    )
    client = RoutingClient(osrm_base=OSRM_BASE, ors_base=ORS_BASE, ors_api_key=None)

    km = client.road_km(start=(45.4642, 9.19), end=(45.50, 9.20))

    assert km == pytest.approx(5.3005, rel=1e-4)


def test_osrm_failure_without_ors_key_raises(mocked_responses):
    mocked_responses.get(
        OSRM_URL,
        status=503,
        match=[matchers.query_param_matcher({"overview": "false"})],
    )
    client = RoutingClient(osrm_base=OSRM_BASE, ors_base=ORS_BASE, ors_api_key=None)

    with pytest.raises(RoutingError):
        client.road_km(start=(45.4642, 9.19), end=(45.50, 9.20))


def test_osrm_failure_with_ors_key_falls_back(mocked_responses):
    # OSRM fallisce
    mocked_responses.get(
        OSRM_URL,
        status=503,
        match=[matchers.query_param_matcher({"overview": "false"})],
    )
    # ORS risponde
    mocked_responses.get(
        ORS_URL,
        json={
            "features": [{
                "properties": {"summary": {"distance": 4800.0, "duration": 540}}
            }]
        },
        status=200,
        match=[matchers.query_param_matcher({
            "api_key": "test-key",
            "start": "9.19,45.4642",
            "end": "9.2,45.5",
        })],
    )
    client = RoutingClient(osrm_base=OSRM_BASE, ors_base=ORS_BASE, ors_api_key="test-key")

    km = client.road_km(start=(45.4642, 9.19), end=(45.50, 9.20))

    assert km == pytest.approx(4.8, rel=1e-4)


def test_both_fail_raises_routing_error(mocked_responses):
    mocked_responses.get(
        OSRM_URL,
        status=503,
        match=[matchers.query_param_matcher({"overview": "false"})],
    )
    mocked_responses.get(
        ORS_URL,
        status=500,
        match=[matchers.query_param_matcher({
            "api_key": "test-key",
            "start": "9.19,45.4642",
            "end": "9.2,45.5",
        })],
    )
    client = RoutingClient(osrm_base=OSRM_BASE, ors_base=ORS_BASE, ors_api_key="test-key")

    with pytest.raises(RoutingError):
        client.road_km(start=(45.4642, 9.19), end=(45.50, 9.20))


def test_cache_hit_does_not_call_http_twice(mocked_responses):
    mocked_responses.get(
        OSRM_URL,
        json={"code": "Ok", "routes": [{"distance": 5300.5, "duration": 600}]},
        status=200,
        match=[matchers.query_param_matcher({"overview": "false"})],
    )
    client = RoutingClient(osrm_base=OSRM_BASE, ors_base=ORS_BASE, ors_api_key=None)

    km1 = client.road_km(start=(45.4642, 9.19), end=(45.50, 9.20))
    km2 = client.road_km(start=(45.4642, 9.19), end=(45.50, 9.20))

    assert km1 == km2
    assert len(mocked_responses.calls) == 1  # un solo HTTP, il secondo da cache


def test_invalid_osrm_json_raises_routing_error(mocked_responses):
    mocked_responses.get(
        OSRM_URL,
        json={"code": "NoRoute", "message": "Impossible route"},
        status=200,
        match=[matchers.query_param_matcher({"overview": "false"})],
    )
    client = RoutingClient(osrm_base=OSRM_BASE, ors_base=ORS_BASE, ors_api_key=None)

    with pytest.raises(RoutingError):
        client.road_km(start=(45.4642, 9.19), end=(45.50, 9.20))
