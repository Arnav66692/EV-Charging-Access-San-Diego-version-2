"""Swapping the demand layer changes DCFC scores and leaves L2 unchanged. The
DAC access ratio matches a hand computed value."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from src.access.dac_ratio import dac_access_ratio, weighted_median
from src.access.od_cost import EuclideanODProvider
from src.access.scores import compute_surfaces

MILE_M = 1609.344
CENTER = (-117.10, 32.70)
M_PER_DEG_LAT = 110900.0
M_PER_DEG_LON = 93660.0


def _pt(east_m, north_m):
    return Point(CENTER[0] + east_m / M_PER_DEG_LON, CENTER[1] + north_m / M_PER_DEG_LAT)


def _demand_swap_inputs():
    origins = gpd.GeoDataFrame(
        {
            "origin_id": ["060730001001", "060730001002", "060730001003"],
            "geoid_bg": ["060730001001", "060730001002", "060730001003"],
        },
        geometry=[_pt(0, 500), _pt(500, 0), _pt(0, -500)],
        crs="EPSG:4326",
    )
    dcfc = gpd.GeoDataFrame(
        {"supply_id": ["s1", "s2"], "capacity": [5.0, 3.0]},
        geometry=[_pt(0, 0), _pt(1000, 0)],
        crs="EPSG:4326",
    )
    l2 = gpd.GeoDataFrame(
        {"supply_id": ["l1"], "capacity": [4.0]},
        geometry=[_pt(0, 0)],
        crs="EPSG:4326",
    )
    demand = {
        "residential": pd.Series(
            {"060730001001": 100.0, "060730001002": 100.0, "060730001003": 100.0}
        ),
        # Workplace jobs are concentrated, a different distribution from residents.
        "lodes_wac": pd.Series(
            {"060730001001": 500.0, "060730001002": 10.0, "060730001003": 10.0}
        ),
    }
    thresholds = {"dcfc": 6.0 * MILE_M, "l2": 2.0 * MILE_M}
    return origins, {"dcfc": dcfc, "l2": l2}, demand, thresholds


def test_swapping_demand_changes_dcfc_not_l2(e2_params):
    origins, supplies, demand, thresholds = _demand_swap_inputs()
    provider = EuclideanODProvider()
    c2t = {"06073": "sdge"}

    common = dict(
        origins=origins,
        supplies_by_type=supplies,
        demand_by_spec=demand,
        provider=provider,
        thresholds_by_type=thresholds,
        methods=["g2sfca"],
        county_to_territory=c2t,
        e2_params=e2_params,
        mode="euclidean",
    )
    run_a = compute_surfaces(type_specs={"dcfc": ["residential"], "l2": ["residential"]}, **common)
    run_b = compute_surfaces(type_specs={"dcfc": ["lodes_wac"], "l2": ["residential"]}, **common)

    def access_map(df, charger_type):
        sub = df[df["charger_type"] == charger_type]
        return dict(zip(sub["geoid_bg"], sub["access"]))

    # L2 uses residential in both runs, so its surface is identical.
    assert access_map(run_a, "l2") == access_map(run_b, "l2")

    # DCFC demand changed from residential to workplace jobs, so DCFC moves.
    dcfc_a = access_map(run_a, "dcfc")
    dcfc_b = access_map(run_b, "dcfc")
    assert dcfc_a.keys() == dcfc_b.keys()
    assert any(abs(dcfc_a[k] - dcfc_b[k]) > 1e-9 for k in dcfc_a)


def test_weighted_median_even_split_averages():
    # Two equal weight points straddle the half mark, so the median averages them.
    assert weighted_median([0.5, 0.9], [200, 200]) == pytest.approx(0.7)
    # Unequal weights put the half mark inside the heavier value.
    assert weighted_median([0.2, 0.4], [100, 300]) == pytest.approx(0.4)


def test_dac_access_ratio_hand_computed():
    scores_long = pd.DataFrame(
        {
            "geoid_bg": ["a", "b", "c", "d"],
            "territory": ["sdge"] * 4,
            "charger_type": ["dcfc"] * 4,
            "method": ["g2sfca"] * 4,
            "demand_spec": ["residential"] * 4,
            "access": [0.2, 0.4, 0.5, 0.9],
        }
    )
    dac_flags = pd.Series({"a": True, "b": True, "c": False, "d": False}, dtype="boolean")
    population = pd.Series({"a": 100.0, "b": 300.0, "c": 200.0, "d": 200.0})

    out = dac_access_ratio(scores_long, dac_flags, population)
    row = out.iloc[0]
    # DAC weighted median over [0.2 w100, 0.4 w300] is 0.4.
    # Non DAC weighted median over [0.5 w200, 0.9 w200] is 0.7.
    assert row["dac_weighted_median"] == pytest.approx(0.4)
    assert row["non_dac_weighted_median"] == pytest.approx(0.7)
    assert row["dac_access_ratio"] == pytest.approx(0.4 / 0.7, rel=1e-6)
