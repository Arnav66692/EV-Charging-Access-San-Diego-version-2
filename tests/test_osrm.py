"""The OSRM client returns positive finite drive times for the smoke test pairs.

OSRM is mocked here so the test runs without a live routing server. The live
smoke test against a real instance lives in src/routing/osrm_client.smoke_test.
"""

from __future__ import annotations

import re

import responses

from src.routing.osrm_client import (
    SAN_DIEGO_SMOKE_PAIRS,
    OSRMClient,
    smoke_test,
)

BASE_URL = "http://localhost:5000"
ROUTE_PATTERN = re.compile(r"http://localhost:5000/route/v1/driving/.*")
TABLE_PATTERN = re.compile(r"http://localhost:5000/table/v1/driving/.*")


def _route_response(request):
    # A plausible positive duration and distance for any pair.
    body = {
        "code": "Ok",
        "routes": [{"duration": 540.3, "distance": 7320.8}],
        "waypoints": [],
    }
    import json

    return (200, {}, json.dumps(body))


@responses.activate
def test_route_returns_positive_finite_drive_time():
    responses.add_callback(
        responses.GET, ROUTE_PATTERN, callback=_route_response, content_type="application/json"
    )
    client = OSRMClient(base_url=BASE_URL)
    origin, destination = SAN_DIEGO_SMOKE_PAIRS[0]
    result = client.route(origin, destination)
    assert result.is_valid
    assert result.duration_s > 0
    assert result.distance_m > 0
    assert result.duration_min > 0


@responses.activate
def test_smoke_test_all_pairs_valid():
    responses.add_callback(
        responses.GET, ROUTE_PATTERN, callback=_route_response, content_type="application/json"
    )
    client = OSRMClient(base_url=BASE_URL)
    results = smoke_test(client)
    assert len(results) == len(SAN_DIEGO_SMOKE_PAIRS)
    for r in results:
        assert r.is_valid
        assert r.duration_s > 0


@responses.activate
def test_table_batch_returns_matrices():
    def _table_response(request):
        import json

        body = {
            "code": "Ok",
            "durations": [[0.0, 540.3], [560.1, 0.0]],
            "distances": [[0.0, 7320.8], [7400.2, 0.0]],
        }
        return (200, {}, json.dumps(body))

    responses.add_callback(
        responses.GET, TABLE_PATTERN, callback=_table_response, content_type="application/json"
    )
    client = OSRMClient(base_url=BASE_URL)
    origins = [p[0] for p in SAN_DIEGO_SMOKE_PAIRS[:2]]
    matrices = client.table(origins)
    assert len(matrices["durations"]) == 2
    assert matrices["durations"][0][1] > 0


@responses.activate
def test_health_true_when_instance_answers():
    responses.add_callback(
        responses.GET, ROUTE_PATTERN, callback=_route_response, content_type="application/json"
    )
    client = OSRMClient(base_url=BASE_URL)
    assert client.health() is True
