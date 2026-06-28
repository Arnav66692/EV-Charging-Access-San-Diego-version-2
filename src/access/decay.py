"""Distance decay functions for the SFCA family.

Two forms are provided.

G2SFCA uses the normalized Gaussian of Dai 2010. For a cost d within the
threshold d0 the weight is

    w = (exp(-0.5 (d/d0)^2) - exp(-0.5)) / (1 - exp(-0.5))

which is 1 at d equal to 0 and 0 at d equal to d0. Beyond d0 the weight is 0.

E2SFCA uses discrete distance decay zones, Luo and Qi 2009. Each zone covers a
band of d over d0 and carries a fixed Gaussian derived weight.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np

_GAUSS_FLOOR = math.exp(-0.5)
_GAUSS_RANGE = 1.0 - _GAUSS_FLOOR


def gaussian_g2sfca(cost: np.ndarray, d0: float) -> np.ndarray:
    """Vectorised normalized Gaussian decay, Dai 2010. Zero beyond the threshold."""
    cost = np.asarray(cost, dtype="float64")
    ratio = cost / d0
    raw = (np.exp(-0.5 * ratio * ratio) - _GAUSS_FLOOR) / _GAUSS_RANGE
    return np.where(cost <= d0, np.clip(raw, 0.0, 1.0), 0.0)


def e2sfca_zone(
    cost: np.ndarray,
    d0: float,
    zone_breaks: Sequence[float],
    zone_weights: Sequence[float],
) -> np.ndarray:
    """Vectorised discrete zone decay, Luo and Qi 2009.

    zone_breaks are increasing fractions of the threshold, ending at 1.0. A cost
    falls in the first zone whose break it does not exceed, and takes that zone
    weight. Beyond the threshold the weight is 0.
    """
    if len(zone_breaks) != len(zone_weights):
        raise ValueError("zone_breaks and zone_weights must have equal length")
    cost = np.asarray(cost, dtype="float64")
    ratio = cost / d0
    weight = np.zeros_like(ratio)
    assigned = np.zeros_like(ratio, dtype=bool)
    # Walk zones from inner to outer. The first matching break wins.
    for brk, wt in zip(zone_breaks, zone_weights):
        in_zone = (~assigned) & (ratio <= brk)
        weight = np.where(in_zone, wt, weight)
        assigned = assigned | in_zone
    # Anything beyond the last break, which is the threshold, stays 0.
    return weight


def scalar_gaussian_g2sfca(cost: float, d0: float) -> float:
    """Scalar convenience form, useful in tests and documentation."""
    return float(gaussian_g2sfca(np.array([cost]), d0)[0])
