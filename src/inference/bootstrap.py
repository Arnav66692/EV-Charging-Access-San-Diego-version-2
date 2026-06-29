"""Spatial block bootstrap.

Access values in nearby block groups are spatially autocorrelated, so an iid
resample of block groups understates the variance. The block bootstrap resamples
spatial blocks instead. The block here is the census tract, the first 11 digits of
the block group GEOID. Block groups in the same tract are resampled together, so
the within tract correlation is preserved.

Each resample draws tracts with replacement until the original tract count is
reached, then takes all block groups in the drawn tracts. A statistic is computed
on each resample. The percentile interval of the statistics is the confidence
interval.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd


def tract_of(geoid_bg: pd.Series) -> pd.Series:
    """The census tract block, the first 11 digits of the block group GEOID."""
    return geoid_bg.astype(str).str[:11]


def block_bootstrap(
    frame: pd.DataFrame,
    statistic: Callable[[pd.DataFrame], float],
    n_resamples: int = 2000,
    seed: int = 12345,
    block_col: str = "tract",
) -> np.ndarray:
    """Return the statistic over n spatial block resamples.

    frame must carry the block column. Tracts are drawn with replacement to the
    original tract count, and all rows in the drawn tracts form the resample.
    """
    frame = frame.reset_index(drop=True)
    if block_col not in frame.columns:
        frame[block_col] = tract_of(frame["geoid_bg"])
    # Precompute the row indices of each block once, then resample by index so each
    # draw is a fast iloc rather than a concat of frames.
    idx_by_block = [g.index.to_numpy() for _, g in frame.groupby(block_col)]
    n_blocks = len(idx_by_block)
    rng = np.random.default_rng(seed)

    out = np.empty(n_resamples, dtype="float64")
    for r in range(n_resamples):
        drawn = rng.integers(0, n_blocks, size=n_blocks)
        idx = np.concatenate([idx_by_block[b] for b in drawn])
        out[r] = statistic(frame.iloc[idx])
    return out


def percentile_ci(samples: np.ndarray, level: float = 0.95) -> tuple[float, float]:
    """Percentile confidence interval, ignoring NaN resamples."""
    valid = samples[~np.isnan(samples)]
    if valid.size == 0:
        return (float("nan"), float("nan"))
    alpha = (1.0 - level) / 2.0
    return (float(np.quantile(valid, alpha)), float(np.quantile(valid, 1.0 - alpha)))


def excludes(ci: tuple[float, float], value: float) -> bool:
    """True if the interval lies entirely on one side of value, parity test."""
    lo, hi = ci
    if np.isnan(lo) or np.isnan(hi):
        return False
    return hi < value or lo > value
