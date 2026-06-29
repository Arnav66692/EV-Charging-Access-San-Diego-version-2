"""Grid feasibility classifier. Honest redaction handling, tier monotonicity,
and row conservation."""

from __future__ import annotations

import pandas as pd
import pytest

from src.join.grid_feasibility import classify_feasibility, tier_requirements
from src.config import load_config

TIERS = {"small": 0.3, "medium": 0.6, "large": 2.8}


def _joined():
    # c1 ample, c2 small-only, c3 redacted (null mw), c4 no section (unjoined).
    return pd.DataFrame(
        {
            "candidate_id": ["c1", "c2", "c3", "c4"],
            "county_fips": ["06037", "06059", "06037", "06059"],
            "joined_flag": [True, True, True, False],
            "load_capacity_mw": [3.0, 0.5, None, None],
        }
    )


def test_tier_requirements_from_config():
    tiers = tier_requirements(load_config())
    assert tiers["small"] == pytest.approx(0.3)
    assert tiers["medium"] == pytest.approx(0.6)
    assert tiers["large"] == pytest.approx(2.8)


def test_capacity_unknown_never_feasible():
    out = classify_feasibility(_joined(), TIERS).set_index("candidate_id")
    # Redacted and no-section candidates are unknown, never feasible or infeasible.
    for cid, reason in [("c3", "capacity_redacted"), ("c4", "no_section_within_threshold")]:
        assert bool(out.loc[cid, "capacity_unknown"]) is True
        assert out.loc[cid, "grid_status"] == reason
        for tier in TIERS:
            assert pd.isna(out.loc[cid, f"feasible_{tier}"])
    # Known candidates are not flagged unknown.
    assert bool(out.loc["c1", "capacity_unknown"]) is False
    assert bool(out.loc["c2", "capacity_unknown"]) is False


def test_tier_monotonicity():
    out = classify_feasibility(_joined(), TIERS).set_index("candidate_id")
    # c1 has 3.0 MW: feasible at every tier.
    assert bool(out.loc["c1", "feasible_large"]) is True
    assert bool(out.loc["c1", "feasible_medium"]) is True
    assert bool(out.loc["c1", "feasible_small"]) is True
    # c2 has 0.5 MW: small only.
    assert bool(out.loc["c2", "feasible_small"]) is True
    assert bool(out.loc["c2", "feasible_medium"]) is False
    assert bool(out.loc["c2", "feasible_large"]) is False
    # General monotonicity over all classified rows: large implies medium implies small.
    known = out[~out["capacity_unknown"]]
    for _, r in known.iterrows():
        if r["feasible_large"]:
            assert r["feasible_medium"] and r["feasible_small"]
        if r["feasible_medium"]:
            assert r["feasible_small"]


def test_row_conservation():
    joined = _joined()
    out = classify_feasibility(joined, TIERS)
    assert len(out) == len(joined)
    assert set(out["candidate_id"]) == set(joined["candidate_id"])
    # Every input candidate appears exactly once in the output.
    assert out["candidate_id"].is_unique
