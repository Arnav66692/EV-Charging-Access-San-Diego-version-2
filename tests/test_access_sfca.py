"""SFCA math reproduces a hand computed answer, and the three methods are not
aliased."""

from __future__ import annotations

import pandas as pd
import pytest

from src.access.decay import e2sfca_zone, scalar_gaussian_g2sfca
from src.access.od_types import ODStructure
from src.access.sfca import access_all_methods, access_scores

# Hand computed answers for the cost-0 toy. With cost 0 every decay weight is 1.
# G2SFCA and E2SFCA both reduce to the plain two step gravity, so they coincide.
# 3SFCA differs because of the Huff selection weight.
EXPECTED_G2 = {"b1": 0.01666667, "b2": 0.02333333, "b3": 0.01000000, "b4": 0.00666667}
EXPECTED_3SFCA = {
    "b1": 0.02470588,
    "b2": 0.01649087,
    "b3": 0.00973631,
    "b4": 0.00827586,
}


def test_g2sfca_matches_hand_computed(sfca_toy, e2_params):
    access = access_scores(
        sfca_toy["od"], sfca_toy["supply"], sfca_toy["demand"], "g2sfca",
        e2_params, sfca_toy["all_origins"],
    )
    for bg, expected in EXPECTED_G2.items():
        assert access[bg] == pytest.approx(expected, rel=1e-4)


def test_e2sfca_matches_hand_computed(sfca_toy, e2_params):
    # Cost 0 lands in the inner zone with weight 1, so E2SFCA equals G2SFCA here.
    access = access_scores(
        sfca_toy["od"], sfca_toy["supply"], sfca_toy["demand"], "e2sfca",
        e2_params, sfca_toy["all_origins"],
    )
    for bg, expected in EXPECTED_G2.items():
        assert access[bg] == pytest.approx(expected, rel=1e-4)


def test_3sfca_matches_hand_computed(sfca_toy, e2_params):
    access = access_scores(
        sfca_toy["od"], sfca_toy["supply"], sfca_toy["demand"], "3sfca",
        e2_params, sfca_toy["all_origins"],
    )
    for bg, expected in EXPECTED_3SFCA.items():
        assert access[bg] == pytest.approx(expected, rel=1e-4)


def test_three_methods_are_distinct_surfaces(e2_params):
    # Nonzero costs spread across the E2SFCA zones make the continuous Gaussian,
    # the discrete zone, and the Huff weighted method produce three different
    # surfaces. This guards against the methods being accidentally aliased.
    d0 = 10.0
    pairs = pd.DataFrame(
        {
            "origin_id": ["b1", "b1", "b2", "b2", "b3", "b3"],
            "supply_id": ["s1", "s2", "s1", "s2", "s1", "s2"],
            "cost": [1.0, 8.0, 4.0, 2.0, 9.0, 5.0],
        }
    )
    od = ODStructure(pairs=pairs, cost_unit="minutes", threshold=d0, backend="test")
    supply = pd.Series({"s1": 5.0, "s2": 3.0})
    demand = pd.Series({"b1": 100.0, "b2": 150.0, "b3": 200.0})
    methods = ["g2sfca", "e2sfca", "3sfca"]

    wide = access_all_methods(od, supply, demand, methods, e2_params, ["b1", "b2", "b3"])

    g2 = wide["g2sfca"]
    e2 = wide["e2sfca"]
    s3 = wide["3sfca"]
    assert not g2.equals(e2)
    assert not g2.equals(s3)
    assert not e2.equals(s3)
    # All three are real surfaces with positive access somewhere.
    for col in methods:
        assert (wide[col] > 0).any()


def test_gaussian_decay_endpoints():
    d0 = 10.0
    assert scalar_gaussian_g2sfca(0.0, d0) == pytest.approx(1.0)
    assert scalar_gaussian_g2sfca(d0, d0) == pytest.approx(0.0)
    assert scalar_gaussian_g2sfca(2 * d0, d0) == 0.0  # beyond threshold is zero
    # Midpoint matches the Dai 2010 normalized form, computed independently.
    mid = scalar_gaussian_g2sfca(5.0, d0)
    import math
    expected = (math.exp(-0.5 * 0.25) - math.exp(-0.5)) / (1 - math.exp(-0.5))
    assert mid == pytest.approx(expected, rel=1e-9)


def test_e2sfca_zone_weights():
    d0 = 10.0
    breaks = [0.3333, 0.6667, 1.0]
    weights = [1.0, 0.68, 0.22]
    # Costs of 2, 5, and 9 fall in the inner, middle, and outer zones.
    out = e2sfca_zone([2.0, 5.0, 9.0, 11.0], d0, breaks, weights)
    assert list(out) == [1.0, 0.68, 0.22, 0.0]
