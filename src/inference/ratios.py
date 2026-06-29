"""Equity ratios on an access surface. DAC, renter, and multifamily.

A ratio compares the population weighted median access of one group to another.
The DAC ratio is DAC over non DAC. The renter and multifamily ratios are the top
quartile over the bottom quartile of the renter share and the multifamily share.
A ratio below 1 means the disadvantaged group has lower typical access.

These are pure functions over a tidy frame, so the bootstrap can call them on each
resample.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.access.dac_ratio import weighted_median

# B25024 unit in structure categories that count as multifamily, two or more
# units in the structure. 004 is 2 units, through 009 which is 50 or more.
MULTIFAMILY_FIELDS = [f"B25024_00{n}E" for n in range(4, 10)]


def renter_share(acs: pd.DataFrame) -> pd.Series:
    """Renter occupied share, B25003_003E over B25003_001E, indexed by geoid_bg."""
    total = pd.to_numeric(acs["B25003_001E"], errors="coerce")
    renter = pd.to_numeric(acs["B25003_003E"], errors="coerce")
    share = (renter / total).where(total > 0)
    return pd.Series(share.to_numpy(), index=acs["geoid_bg"].astype(str), name="renter_share")


def multifamily_share(acs: pd.DataFrame) -> pd.Series:
    """Multifamily share, units in 2 or more unit structures over total units."""
    total = pd.to_numeric(acs["B25024_001E"], errors="coerce")
    mf = sum(pd.to_numeric(acs[f], errors="coerce").fillna(0) for f in MULTIFAMILY_FIELDS)
    share = (mf / total).where(total > 0)
    return pd.Series(share.to_numpy(), index=acs["geoid_bg"].astype(str), name="multifamily_share")


def dac_ratio(frame: pd.DataFrame) -> float:
    """DAC over non DAC population weighted median access.

    frame needs access, is_dac, and weight columns. Returns NaN if a side is empty.
    """
    dac = frame[frame["is_dac"] == True]  # noqa: E712
    non = frame[frame["is_dac"] == False]
    dm = weighted_median(dac["access"].to_numpy(), dac["weight"].to_numpy())
    nm = weighted_median(non["access"].to_numpy(), non["weight"].to_numpy())
    if not nm or np.isnan(nm) or nm == 0:
        return float("nan")
    return float(dm / nm)


def quartile_ratio(frame: pd.DataFrame, score_col: str) -> float:
    """Top quartile over bottom quartile of a score, weighted median access ratio.

    Used for the renter and multifamily contrasts. The quartile cut is on the
    score, the access medians are population weighted within each quartile.
    """
    f = frame.dropna(subset=[score_col, "access", "weight"])
    if len(f) < 8:
        return float("nan")
    q1, q4 = f[score_col].quantile(0.25), f[score_col].quantile(0.75)
    low = f[f[score_col] <= q1]
    high = f[f[score_col] >= q4]
    lm = weighted_median(low["access"].to_numpy(), low["weight"].to_numpy())
    hm = weighted_median(high["access"].to_numpy(), high["weight"].to_numpy())
    if not lm or np.isnan(lm) or lm == 0:
        return float("nan")
    # High score group over low score group. Renters and multifamily are the high
    # group, so a ratio below 1 means they have lower access.
    return float(hm / lm)
