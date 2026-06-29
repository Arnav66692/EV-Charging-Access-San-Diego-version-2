"""The spatial block bootstrap is reproducible under a fixed seed and its interval
brackets the point estimate."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.inference.bootstrap import block_bootstrap, excludes, percentile_ci, tract_of
from src.inference.ratios import dac_ratio


def _frame():
    # Six tracts, two block groups each. DAC areas have systematically lower
    # access, so the point ratio is below 1.
    rows = []
    rng = np.random.default_rng(0)
    for t in range(6):
        is_dac = t < 3
        base = 0.001 if is_dac else 0.002
        for bg in range(2):
            geoid = f"06073{t:06d}{bg}"
            rows.append(
                {
                    "geoid_bg": geoid,
                    "access": base + rng.normal(0, 0.00005),
                    "is_dac": bool(is_dac),
                    "weight": 1000.0,
                }
            )
    df = pd.DataFrame(rows)
    df["tract"] = tract_of(df["geoid_bg"])
    return df


def test_block_uses_tract():
    df = _frame()
    # Two block groups per tract collapse to one tract block.
    assert df["tract"].nunique() == 6
    assert (df["tract"].str.len() == 11).all()


def test_bootstrap_reproducible_under_seed():
    df = _frame()
    a = block_bootstrap(df, dac_ratio, n_resamples=200, seed=42)
    b = block_bootstrap(df, dac_ratio, n_resamples=200, seed=42)
    assert np.array_equal(a, b, equal_nan=True)
    c = block_bootstrap(df, dac_ratio, n_resamples=200, seed=43)
    assert not np.array_equal(a, c, equal_nan=True)


def test_ci_brackets_point_estimate():
    df = _frame()
    point = dac_ratio(df)
    samples = block_bootstrap(df, dac_ratio, n_resamples=500, seed=7)
    lo, hi = percentile_ci(samples, level=0.95)
    assert lo <= point <= hi
    # The DAC areas were built lower, so the ratio is below 1.
    assert point < 1.0


def test_excludes_parity_helper():
    assert excludes((0.5, 0.8), 1.0) is True  # entirely below parity
    assert excludes((0.9, 1.2), 1.0) is False  # straddles parity
    assert excludes((1.1, 1.3), 1.0) is True  # entirely above parity
