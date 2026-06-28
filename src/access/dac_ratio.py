"""Descriptive disadvantaged community access ratio.

The estimand is the population weighted median access in DAC block groups over
the population weighted median access in non DAC block groups, computed per
territory, charger type, and method. This is the v1 estimand. It is descriptive
only. The bootstrap and the robustness sweeps are Phase 4.

A ratio below 1 means DAC block groups have lower typical access.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    """Population weighted median.

    The weighted median is the value where the cumulative weight first reaches
    half of the total weight. Ties at the boundary average the two flanking
    values, matching the usual lower and upper median convention.
    """
    values = np.asarray(values, dtype="float64")
    weights = np.asarray(weights, dtype="float64")
    keep = ~np.isnan(values) & (weights > 0)
    values, weights = values[keep], weights[keep]
    if values.size == 0:
        return float("nan")
    order = np.argsort(values)
    values, weights = values[order], weights[order]
    cum = np.cumsum(weights)
    half = 0.5 * cum[-1]
    idx = int(np.searchsorted(cum, half, side="left"))
    # When the cumulative weight lands exactly on the half point, the median sits
    # between this value and the next, so average them. Otherwise this value
    # spans the half point and is the median.
    if cum[idx] == half and idx + 1 < values.size:
        return float((values[idx] + values[idx + 1]) / 2.0)
    return float(values[idx])


def dac_access_ratio(
    scores_long: pd.DataFrame,
    dac_flags: pd.Series,
    population: pd.Series,
    group_cols: tuple[str, ...] = ("territory", "charger_type", "method", "demand_spec"),
) -> pd.DataFrame:
    """Compute the DAC access ratio for each reporting group.

    scores_long needs geoid_bg, access, and the group columns. dac_flags and
    population are indexed by geoid_bg.
    """
    df = scores_long.copy()
    df["geoid_bg"] = df["geoid_bg"].astype(str)
    df["dac_flag"] = df["geoid_bg"].map(dac_flags.rename(None))
    df["weight"] = df["geoid_bg"].map(population.rename(None)).astype(float)

    present = [c for c in group_cols if c in df.columns]
    rows = []
    for keys, sub in df.groupby(list(present)):
        keys = keys if isinstance(keys, tuple) else (keys,)
        dac = sub[sub["dac_flag"] == True]  # noqa: E712, nullable boolean compare
        non = sub[sub["dac_flag"] == False]
        dac_med = weighted_median(dac["access"].to_numpy(), dac["weight"].to_numpy())
        non_med = weighted_median(non["access"].to_numpy(), non["weight"].to_numpy())
        ratio = dac_med / non_med if non_med and not np.isnan(non_med) and non_med != 0 else float("nan")
        record = dict(zip(present, keys))
        record.update(
            {
                "dac_weighted_median": dac_med,
                "non_dac_weighted_median": non_med,
                "dac_access_ratio": ratio,
                "n_dac": int(len(dac)),
                "n_non_dac": int(len(non)),
            }
        )
        rows.append(record)
    return pd.DataFrame(rows)
