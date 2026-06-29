"""The siting optimizer respects feasibility and budget, and the gap-closing
objective never makes DAC areas worse off."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

from src.access.dac_ratio import weighted_median
from src.optimize.marginal import candidate_coefficients, portfolio_delta_access
from src.optimize.siting import solve_siting

TIER_PORTS = {"small": 2, "medium": 4, "large": 8}
D0_M = 6.0 * 1609.344


def _scene():
    # Two clusters far apart. A DAC cluster around candidate A, a non-DAC cluster
    # around candidate B, and U is capacity_unknown so it is never selectable.
    centroids = gpd.GeoDataFrame(
        {"geoid_bg": ["b1", "b2", "b3", "b4"]},
        geometry=[
            Point(-117.100, 32.70), Point(-117.101, 32.70),  # DAC, near A
            Point(-117.400, 32.70), Point(-117.401, 32.70),  # non-DAC, near B
        ],
        crs="EPSG:4326",
    )
    population = pd.Series({"b1": 1000.0, "b2": 1000.0, "b3": 1000.0, "b4": 1000.0})
    dac = pd.Series({"b1": True, "b2": True, "b3": False, "b4": False}, dtype="boolean")
    candidates = gpd.GeoDataFrame(
        {"candidate_id": ["A", "B", "U"]},
        geometry=[Point(-117.1005, 32.70), Point(-117.4005, 32.70), Point(-117.70, 32.90)],
        crs="EPSG:4326",
    )
    feasibility = pd.DataFrame(
        {
            "candidate_id": ["A", "B", "U"],
            "capacity_unknown": [False, False, True],
            "feasible_small": pd.array([True, True, pd.NA], dtype="boolean"),
            "feasible_medium": pd.array([True, False, pd.NA], dtype="boolean"),
            "feasible_large": pd.array([False, False, pd.NA], dtype="boolean"),
        }
    )
    return centroids, candidates, feasibility, population, dac


def _coeffs():
    c, cand, feas, pop, dac = _scene()
    return candidate_coefficients(c, cand, feas, pop, dac, D0_M, TIER_PORTS, 2.0)


def test_coefficients_exclude_unknown_and_infeasible():
    coeffs = _coeffs()
    # U is capacity_unknown, never appears. A has small and medium, B has small.
    assert "U" not in set(coeffs["candidate_id"])
    a_tiers = set(coeffs[coeffs.candidate_id == "A"]["tier"])
    b_tiers = set(coeffs[coeffs.candidate_id == "B"]["tier"])
    assert a_tiers == {"small", "medium"}
    assert b_tiers == {"small"}
    # A is by the DAC cluster, so its gap coefficient is positive. B has none.
    assert coeffs[coeffs.candidate_id == "A"]["coef_gap"].max() > 0
    assert coeffs[coeffs.candidate_id == "B"]["coef_gap"].max() == 0


def test_optimizer_respects_budget_and_feasibility():
    coeffs = _coeffs()
    res = solve_siting(coeffs, budget_ports=4, objective="gap_closing")
    # Budget respected.
    assert res.ports_used <= 4
    # Only feasible candidate tier pairs selected, never the unknown site.
    sel = set(zip(res.selected["candidate_id"], res.selected["tier"]))
    allowed = set(zip(coeffs["candidate_id"], coeffs["tier"]))
    assert sel.issubset(allowed)
    assert "U" not in set(res.selected["candidate_id"])
    # One tier per site.
    assert res.selected["candidate_id"].is_unique
    # The gap objective picks the DAC adjacent site A, not the zero-value B.
    assert "A" in set(res.selected["candidate_id"])


def test_gap_closing_never_increases_dac_gap():
    centroids, candidates, feasibility, population, dac = _scene()
    coeffs = candidate_coefficients(
        centroids, candidates, feasibility, population, dac, D0_M, TIER_PORTS, 2.0
    )
    res = solve_siting(coeffs, budget_ports=4, objective="gap_closing")
    delta = portfolio_delta_access(res.selected, centroids, candidates, population, D0_M, TIER_PORTS)

    # The marginal access is never negative.
    assert (delta.to_numpy() >= 0).all()

    # Baseline access is uniform, so the gap is zero to start. With the gap-closing
    # build the DAC areas gain and the non-DAC areas do not, so the DAC deficit
    # cannot grow. DAC median access with the build is at least the baseline.
    base = pd.Series(0.001, index=delta.index)
    with_build = base + delta
    ids = delta.index.to_numpy()
    isdac = dac.reindex(ids).fillna(False).astype(bool).to_numpy()
    w = population.reindex(ids).fillna(0).to_numpy()
    dac_base = weighted_median(base.to_numpy()[isdac], w[isdac])
    dac_with = weighted_median(with_build.to_numpy()[isdac], w[isdac])
    non_with = weighted_median(with_build.to_numpy()[~isdac], w[~isdac])
    assert dac_with >= dac_base  # DAC areas never worse off
    # Non-DAC did not gain here, so the gap, non-DAC minus DAC, did not increase.
    gap_base = weighted_median(base.to_numpy()[~isdac], w[~isdac]) - dac_base
    gap_with = non_with - dac_with
    assert gap_with <= gap_base + 1e-12


def test_selected_rows_conserved_subset():
    coeffs = _coeffs()
    res = solve_siting(coeffs, budget_ports=100, objective="total_gain")
    # Every selected pair is a real candidate tier, no fabricated rows.
    sel = set(zip(res.selected["candidate_id"], res.selected["tier"]))
    assert sel.issubset(set(zip(coeffs["candidate_id"], coeffs["tier"])))
    assert len(res.selected) == res.n_selected
