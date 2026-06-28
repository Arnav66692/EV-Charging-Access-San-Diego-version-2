"""Thin OSRM client.

Returns drive time and drive distance for an origin destination pair or a small
batch, against a local OSRM car profile instance. Coordinates are (lon, lat)
tuples, matching OSRM and GeoJSON axis order.

The pair path uses the OSRM route service. The batch path uses the table
service with duration and distance annotations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import requests

from src.config import load_config

# A few known San Diego origin destination pairs for the smoke test.
# Coordinates are (lon, lat). Downtown, the airport, Balboa Park, La Jolla, SDSU.
SAN_DIEGO_SMOKE_PAIRS: tuple[tuple[tuple[float, float], tuple[float, float]], ...] = (
    ((-117.1611, 32.7157), (-117.1933, 32.7336)),  # downtown to airport
    ((-117.1611, 32.7157), (-117.1466, 32.7341)),  # downtown to Balboa Park
    ((-117.2713, 32.8328), (-117.0700, 32.7757)),  # La Jolla to SDSU
)

Coord = tuple[float, float]


@dataclass(frozen=True)
class RouteResult:
    """A single origin destination routing result."""

    duration_s: float
    distance_m: float

    @property
    def duration_min(self) -> float:
        return self.duration_s / 60.0

    @property
    def is_valid(self) -> bool:
        return (
            self.duration_s is not None
            and math.isfinite(self.duration_s)
            and self.duration_s > 0
            and self.distance_m is not None
            and math.isfinite(self.distance_m)
            and self.distance_m > 0
        )


class OSRMError(RuntimeError):
    """Raised when OSRM returns a non Ok response."""


class OSRMClient:
    """Minimal client for a local OSRM HTTP instance."""

    def __init__(
        self,
        base_url: str | None = None,
        profile: str = "driving",
        timeout_s: int = 30,
        session: requests.Session | None = None,
    ) -> None:
        if base_url is None:
            cfg = load_config()
            base_url = cfg.secret(cfg["osrm"]["base_url_env"]) or cfg["osrm"][
                "default_base_url"
            ]
        self.base_url = base_url.rstrip("/")
        self.profile = profile
        self.timeout_s = timeout_s
        self.session = session or requests.Session()

    @staticmethod
    def _fmt(coord: Coord) -> str:
        lon, lat = coord
        return f"{lon},{lat}"

    def route(self, origin: Coord, destination: Coord) -> RouteResult:
        """Drive time and distance for one origin destination pair."""
        coords = f"{self._fmt(origin)};{self._fmt(destination)}"
        url = f"{self.base_url}/route/v1/{self.profile}/{coords}"
        params = {"overview": "false", "alternatives": "false", "steps": "false"}
        payload = self._get(url, params)
        routes = payload.get("routes") or []
        if not routes:
            raise OSRMError(f"No route found for {origin} to {destination}")
        leg = routes[0]
        return RouteResult(
            duration_s=float(leg["duration"]), distance_m=float(leg["distance"])
        )

    def table(
        self,
        origins: Sequence[Coord],
        destinations: Sequence[Coord] | None = None,
    ) -> dict[str, list[list[float]]]:
        """Duration and distance matrices for a small batch.

        When destinations is None the full origins by origins matrix is returned.
        """
        if destinations is None:
            all_coords = list(origins)
            sources = list(range(len(origins)))
            dests = list(range(len(origins)))
        else:
            all_coords = list(origins) + list(destinations)
            sources = list(range(len(origins)))
            dests = list(range(len(origins), len(origins) + len(destinations)))

        coord_str = ";".join(self._fmt(c) for c in all_coords)
        url = f"{self.base_url}/table/v1/{self.profile}/{coord_str}"
        params = {
            "sources": ";".join(map(str, sources)),
            "destinations": ";".join(map(str, dests)),
            "annotations": "duration,distance",
        }
        payload = self._get(url, params)
        return {
            "durations": payload.get("durations", []),
            "distances": payload.get("distances", []),
        }

    def health(self) -> bool:
        """Return True if the instance answers a trivial route, else False."""
        try:
            result = self.route(*SAN_DIEGO_SMOKE_PAIRS[0])
            return result.is_valid
        except (OSRMError, requests.RequestException):
            return False

    def _get(self, url: str, params: dict) -> dict:
        response = self.session.get(url, params=params, timeout=self.timeout_s)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != "Ok":
            raise OSRMError(f"OSRM returned {payload.get('code')}: {payload.get('message')}")
        return payload


def smoke_test(client: OSRMClient | None = None) -> list[RouteResult]:
    """Route the known San Diego pairs and return their results.

    Raises OSRMError if any pair fails to produce a valid positive drive time.
    """
    client = client or OSRMClient()
    results = []
    for origin, destination in SAN_DIEGO_SMOKE_PAIRS:
        result = client.route(origin, destination)
        if not result.is_valid:
            raise OSRMError(f"Invalid route result for {origin} to {destination}: {result}")
        results.append(result)
    return results


if __name__ == "__main__":
    for r in smoke_test():
        print(f"duration {r.duration_min:.1f} min, distance {r.distance_m/1000:.1f} km")
