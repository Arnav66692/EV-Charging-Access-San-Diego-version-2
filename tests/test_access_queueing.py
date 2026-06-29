"""Queueing supply adjustment. The toggle off recovers the Phase 2 linear scores
exactly, and more ports give a higher availability factor."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from src.access.queueing import (
    availability_factor,
    capacity_series_effective,
    effective_supply,
)
from src.access.sfca import access_scores
from src.config import load_config

CFG = load_config()


def _supply_gdf(caps):
    return gpd.GeoDataFrame(
        {"supply_id": [f"s{i+1}" for i in range(len(caps))], "capacity": [float(c) for c in caps]},
        geometry=[Point(-117.0 - i * 0.01, 32.7) for i in range(len(caps))],
        crs="EPSG:4326",
    )


def test_more_ports_higher_availability_factor():
    # Holding arrival rate per port and service rate fixed, a site with more ports
    # has a higher availability factor, the pooling gain of a larger queue.
    small = availability_factor(2, arrival_rate_per_port=0.9, service_rate=1.5)
    large = availability_factor(8, arrival_rate_per_port=0.9, service_rate=1.5)
    assert 0.0 < small < large <= 1.0


def test_availability_factor_bounds_and_saturation():
    # Zero arrivals means always available.
    assert availability_factor(4, 0.0, 1.5) == 1.0
    # A saturated site, rho >= 1, falls below 1 as the served fraction.
    sat = availability_factor(2, arrival_rate_per_port=3.0, service_rate=1.5)  # rho = 2.0
    assert sat == pytest.approx(0.5, rel=1e-6)


def test_toggle_off_recovers_phase2_linear(sfca_toy, e2_params, monkeypatch):
    # With queueing disabled the availability factor is 1.0 and the effective
    # capacity equals the raw port count, so SFCA scores match Phase 2 exactly.
    monkeypatch.setitem(CFG.data["access"]["queueing"], "enabled", False)
    gdf = _supply_gdf([4, 2, 6])  # ids s1, s2, s3 match the toy supply
    eff = effective_supply(gdf, "dcfc", CFG)
    assert (eff["availability_factor"] == 1.0).all()
    assert (eff["capacity"].to_numpy() == eff["raw_port_count"].to_numpy()).all()

    eff_series = capacity_series_effective(eff)
    raw_series = sfca_toy["supply"]
    for method in ("g2sfca", "e2sfca", "3sfca"):
        a_raw = access_scores(sfca_toy["od"], raw_series, sfca_toy["demand"], method, e2_params, sfca_toy["all_origins"])
        a_eff = access_scores(sfca_toy["od"], eff_series, sfca_toy["demand"], method, e2_params, sfca_toy["all_origins"])
        pd.testing.assert_series_equal(a_raw, a_eff)


def test_toggle_on_reduces_congested_supply(monkeypatch):
    # With queueing enabled, a loaded site's effective capacity is below its raw
    # port count, and the raw count is preserved alongside.
    monkeypatch.setitem(CFG.data["access"]["queueing"], "enabled", True)
    gdf = _supply_gdf([4])
    eff = effective_supply(gdf, "dcfc", CFG)
    assert eff["raw_port_count"].iloc[0] == 4.0
    assert eff["capacity"].iloc[0] < 4.0
    assert 0.0 < eff["availability_factor"].iloc[0] < 1.0
