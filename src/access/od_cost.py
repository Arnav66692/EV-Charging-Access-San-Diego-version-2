"""Origin destination cost layer.

A provider returns the sparse within-catchment OD structure that the SFCA engine
consumes. Two backends share one prefilter.

euclidean. Straight line distance in EPSG:3310. No OSRM. Used for the v1-compat
reproduction gate. Cost unit is meters.

osrm. Drive time and drive distance via the OSRM table service on the Phase 1
instance. The table function is injectable so it mocks cleanly in tests. Cost
unit is minutes.

The KD-tree prefilter must never drop a reachable pair. Network distance is
always at least Euclidean distance. So a Euclidean buffer sized at the threshold
converted at a generous upper bound speed, 70 mph, is a safe superset. Only
prefiltered pairs are routed. Survivors inside the true threshold are kept.
"""

from __future__ import annotations

from typing import Callable, Protocol

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from src.access.od_types import COST, ORIGIN, SUPPLY, ODStructure

WORKING_CRS = "EPSG:3310"
METERS_PER_MILE = 1609.344


def mph_to_m_per_min(mph: float) -> float:
    return mph * METERS_PER_MILE / 60.0


def _xy_3310(gdf: gpd.GeoDataFrame) -> np.ndarray:
    """Return projected coordinates in meters, EPSG:3310, as an N by 2 array."""
    proj = gdf.to_crs(WORKING_CRS)
    return np.column_stack([proj.geometry.x.to_numpy(), proj.geometry.y.to_numpy()])


def _lonlat(gdf: gpd.GeoDataFrame) -> list[tuple[float, float]]:
    """Return lon, lat tuples in EPSG:4326 for OSRM."""
    geo = gdf.to_crs("EPSG:4326")
    return list(zip(geo.geometry.x.to_numpy(), geo.geometry.y.to_numpy()))


def prefilter_candidate_pairs(
    origin_xy: np.ndarray, supply_xy: np.ndarray, radius_m: float
) -> list[tuple[int, int]]:
    """KD-tree prefilter. Return origin and supply index pairs within radius_m.

    This is a pure geometric superset. It never drops a pair whose true cost is
    within the radius, because Euclidean distance is a lower bound on any cost
    derived from a road network.
    """
    if len(origin_xy) == 0 or len(supply_xy) == 0:
        return []
    tree = cKDTree(supply_xy)
    neighbor_lists = tree.query_ball_point(origin_xy, r=radius_m)
    pairs: list[tuple[int, int]] = []
    for oi, supply_idxs in enumerate(neighbor_lists):
        for si in supply_idxs:
            pairs.append((oi, si))
    return pairs


class ODCostProvider(Protocol):
    """Returns the within-catchment OD structure for origins and supplies."""

    def od_within_threshold(
        self, origins: gpd.GeoDataFrame, supplies: gpd.GeoDataFrame, threshold: float
    ) -> ODStructure: ...


class EuclideanODProvider:
    """Straight line cost in EPSG:3310. Cost unit is meters. No OSRM needed."""

    backend = "euclidean"

    def od_within_threshold(
        self, origins: gpd.GeoDataFrame, supplies: gpd.GeoDataFrame, threshold: float
    ) -> ODStructure:
        origin_xy = _xy_3310(origins)
        supply_xy = _xy_3310(supplies)
        origin_ids = origins[ORIGIN].astype(str).to_numpy()
        supply_ids = supplies[SUPPLY].astype(str).to_numpy()

        pairs = prefilter_candidate_pairs(origin_xy, supply_xy, threshold)
        rows = []
        for oi, si in pairs:
            dist = float(np.linalg.norm(origin_xy[oi] - supply_xy[si]))
            if dist <= threshold:
                rows.append((origin_ids[oi], supply_ids[si], dist))
        frame = pd.DataFrame(rows, columns=[ORIGIN, SUPPLY, COST])
        return ODStructure(
            pairs=frame, cost_unit="meters", threshold=float(threshold), backend=self.backend
        )


# A table function takes origin and destination lon, lat lists and returns a
# dict with durations and distances matrices. OSRMClient.table matches this.
TableFn = Callable[[list, list], dict]


class OSRMODProvider:
    """Drive time cost via the OSRM table service, on prefiltered candidate sets.

    table_fn is injectable. In production pass OSRMClient.table. In tests pass a
    mock so the engine never needs a live OSRM or Docker.
    """

    backend = "osrm"

    def __init__(
        self,
        table_fn: TableFn,
        upper_bound_speed_mph: float = 70.0,
        chunk_size: int = 100,
    ) -> None:
        self.table_fn = table_fn
        self.upper_bound_speed_mph = upper_bound_speed_mph
        self.chunk_size = chunk_size

    def od_within_threshold(
        self, origins: gpd.GeoDataFrame, supplies: gpd.GeoDataFrame, threshold: float
    ) -> ODStructure:
        """threshold is in minutes. Cost unit is minutes."""
        origin_xy = _xy_3310(origins)
        supply_xy = _xy_3310(supplies)
        origin_ll = _lonlat(origins)
        supply_ll = _lonlat(supplies)
        origin_ids = origins[ORIGIN].astype(str).to_numpy()
        supply_ids = supplies[SUPPLY].astype(str).to_numpy()

        radius_m = threshold * mph_to_m_per_min(self.upper_bound_speed_mph)
        candidate_pairs = prefilter_candidate_pairs(origin_xy, supply_xy, radius_m)

        # Group candidate supplies by origin so each origin is routed once.
        by_origin: dict[int, list[int]] = {}
        for oi, si in candidate_pairs:
            by_origin.setdefault(oi, []).append(si)

        rows: list[tuple[str, str, float, float]] = []
        origin_indices = sorted(by_origin)
        for start in range(0, len(origin_indices), self.chunk_size):
            chunk = origin_indices[start : start + self.chunk_size]
            # The supplies needed by this chunk, deduplicated and ordered.
            needed = sorted({si for oi in chunk for si in by_origin[oi]})
            if not needed:
                continue
            sources = [origin_ll[oi] for oi in chunk]
            dests = [supply_ll[si] for si in needed]
            result = self.table_fn(sources, dests)
            durations = result.get("durations") or []
            distances = result.get("distances") or []
            dest_pos = {si: pos for pos, si in enumerate(needed)}
            for row_i, oi in enumerate(chunk):
                for si in by_origin[oi]:
                    col = dest_pos[si]
                    dur_s = durations[row_i][col] if durations else None
                    if dur_s is None:
                        continue
                    minutes = float(dur_s) / 60.0
                    if minutes <= threshold:
                        dist_m = (
                            float(distances[row_i][col])
                            if distances and distances[row_i][col] is not None
                            else float("nan")
                        )
                        rows.append((origin_ids[oi], supply_ids[si], minutes, dist_m))

        frame = pd.DataFrame(rows, columns=[ORIGIN, SUPPLY, COST, "distance_m"])
        return ODStructure(
            pairs=frame, cost_unit="minutes", threshold=float(threshold), backend=self.backend
        )
