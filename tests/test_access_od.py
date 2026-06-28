"""The OD cost layer. The KD-tree prefilter never drops a reachable pair, and
the OSRM backend works against a mock so no live OSRM is needed."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pyproj
from shapely.geometry import Point

from src.access.od_cost import (
    EuclideanODProvider,
    OSRMODProvider,
    mph_to_m_per_min,
    prefilter_candidate_pairs,
)

_TO_3310 = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3310", always_xy=True)
MPH_30_M_PER_S = 30.0 * 1609.344 / 3600.0  # a realistic speed, well under 70 mph


def _points(coords):
    return [Point(lon, lat) for lon, lat in coords]


def _origins():
    coords = [(-117.16, 32.71), (-117.10, 32.74), (-117.20, 32.70), (-116.95, 32.80)]
    return gpd.GeoDataFrame(
        {"origin_id": [f"b{i}" for i in range(len(coords))]},
        geometry=_points(coords),
        crs="EPSG:4326",
    )


def _supplies():
    coords = [(-117.161, 32.711), (-117.12, 32.73), (-117.30, 32.65), (-116.96, 32.81)]
    return gpd.GeoDataFrame(
        {"supply_id": [f"s{i}" for i in range(len(coords))], "capacity": [4.0, 2.0, 6.0, 3.0]},
        geometry=_points(coords),
        crs="EPSG:4326",
    )


def _xy(gdf):
    proj = gdf.to_crs("EPSG:3310")
    return np.column_stack([proj.geometry.x.to_numpy(), proj.geometry.y.to_numpy()])


def _brute_force_within(origin_xy, supply_xy, radius):
    out = set()
    for oi in range(len(origin_xy)):
        for si in range(len(supply_xy)):
            if np.linalg.norm(origin_xy[oi] - supply_xy[si]) <= radius:
                out.add((oi, si))
    return out


def test_prefilter_matches_brute_force():
    origins, supplies = _origins(), _supplies()
    ox, sx = _xy(origins), _xy(supplies)
    radius = 5000.0
    prefilter = set(prefilter_candidate_pairs(ox, sx, radius))
    brute = _brute_force_within(ox, sx, radius)
    assert prefilter == brute


def _mock_table(sources, destinations):
    # Duration derived from the true 3310 Euclidean distance at 30 mph, which is
    # below the 70 mph prefilter bound, so no reachable pair can escape the
    # prefilter. Distances are the Euclidean meters.
    sx = np.array([_TO_3310.transform(lon, lat) for lon, lat in sources])
    dx = np.array([_TO_3310.transform(lon, lat) for lon, lat in destinations])
    durations, distances = [], []
    for s in sx:
        drow, dist_row = [], []
        for d in dx:
            dist = float(np.linalg.norm(s - d))
            drow.append(dist / MPH_30_M_PER_S)  # seconds
            dist_row.append(dist)
        durations.append(drow)
        distances.append(dist_row)
    return {"durations": durations, "distances": distances}


def test_osrm_prefilter_drops_zero_reachable_pairs():
    origins, supplies = _origins(), _supplies()
    threshold_min = 10.0

    # Brute force the truly reachable pairs under the mock travel times.
    ox, sx = _xy(origins), _xy(supplies)
    reachable = set()
    for oi in range(len(ox)):
        for si in range(len(sx)):
            dur_min = (np.linalg.norm(ox[oi] - sx[si]) / MPH_30_M_PER_S) / 60.0
            if dur_min <= threshold_min:
                reachable.add((origins["origin_id"][oi], supplies["supply_id"][si]))

    # The prefilter superset must contain every reachable pair.
    radius = threshold_min * mph_to_m_per_min(70.0)
    prefilter = set(prefilter_candidate_pairs(ox, sx, radius))
    reachable_idx = set()
    for oi in range(len(ox)):
        for si in range(len(sx)):
            dur_min = (np.linalg.norm(ox[oi] - sx[si]) / MPH_30_M_PER_S) / 60.0
            if dur_min <= threshold_min:
                reachable_idx.add((oi, si))
    assert reachable_idx.issubset(prefilter)  # zero false negatives

    # The provider keeps exactly the reachable pairs, no more, no less.
    provider = OSRMODProvider(table_fn=_mock_table, upper_bound_speed_mph=70.0)
    od = provider.od_within_threshold(origins, supplies, threshold_min)
    got = set(zip(od.pairs["origin_id"], od.pairs["supply_id"]))
    assert got == reachable
    assert (od.pairs["cost"] <= threshold_min + 1e-9).all()
    assert "distance_m" in od.pairs.columns


def test_euclidean_backend_costs_are_distances():
    origins, supplies = _origins(), _supplies()
    radius = 5000.0
    od = EuclideanODProvider().od_within_threshold(origins, supplies, radius)
    assert od.cost_unit == "meters"
    assert (od.pairs["cost"] <= radius + 1e-6).all()

    ox, sx = _xy(origins), _xy(supplies)
    by_id_o = {oid: i for i, oid in enumerate(origins["origin_id"])}
    by_id_s = {sid: i for i, sid in enumerate(supplies["supply_id"])}
    for _, row in od.pairs.iterrows():
        expected = np.linalg.norm(ox[by_id_o[row["origin_id"]]] - sx[by_id_s[row["supply_id"]]])
        assert row["cost"] == np.float64(expected) or abs(row["cost"] - expected) < 1e-6
