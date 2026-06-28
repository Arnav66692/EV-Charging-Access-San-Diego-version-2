"""Pure SFCA engine. Three methods, no network calls.

The engine consumes an OD structure, a supply series, a demand series, and a
decay specification. It returns a per origin access score. It is fully unit
tested on a synthetic OD matrix with a hand computed answer.

All three methods share one two step gravity core. They differ only in the pair
weight m_ij.

  G2SFCA, Dai 2010.        m_ij = w_ij, normalized Gaussian decay.
  E2SFCA, Luo and Qi 2009. m_ij = w_ij, discrete zone decay.
  3SFCA, Wan et al 2012.   m_ij = G_ij w_ij, where G_ij is the Huff style
                           selection weight that allocates demand across the
                           competing supplies reachable from an origin.

Given m_ij the core is

  step one, supply to demand ratio   R_j = S_j / sum_i m_ij D_i
  step two, accessibility            A_i = sum_j m_ij R_j
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.access.decay import e2sfca_zone, gaussian_g2sfca
from src.access.od_types import COST, ORIGIN, SUPPLY, ODStructure

METHODS = ("g2sfca", "e2sfca", "3sfca")


def _decay_weights(cost: np.ndarray, d0: float, method: str, e2_params: dict) -> np.ndarray:
    """Return the distance decay weight w_ij for each pair, per method."""
    if method in ("g2sfca", "3sfca"):
        return gaussian_g2sfca(cost, d0)
    if method == "e2sfca":
        return e2sfca_zone(
            cost, d0, e2_params["zone_breaks"], e2_params["zone_weights"]
        )
    raise ValueError(f"unknown method {method}, expected one of {METHODS}")


def _selection_weights(pairs: pd.DataFrame, supply: pd.Series) -> np.ndarray:
    """Huff style selection weight G_ij for 3SFCA.

    G_ij = S_j w_ij / sum_k S_k w_ik, summed over supplies k reachable from i.
    It splits each demand across the supplies it can reach, weighted by supply
    size and proximity, which corrects the demand double counting of 2SFCA.
    """
    s_w = supply.reindex(pairs[SUPPLY]).to_numpy() * pairs["w"].to_numpy()
    denom = pd.Series(s_w, index=pairs[ORIGIN].to_numpy()).groupby(level=0).transform("sum")
    denom = denom.to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        g = np.where(denom > 0, s_w / denom, 0.0)
    return g


def access_scores(
    od: ODStructure,
    supply: pd.Series,
    demand: pd.Series,
    method: str,
    e2_params: dict | None = None,
    all_origins: list[str] | None = None,
) -> pd.Series:
    """Compute per origin access scores for one method.

    supply is indexed by supply_id, demand by origin_id. all_origins lets a
    caller pin the full origin set so origins with no reachable supply still
    appear, with a score of 0.
    """
    if method not in METHODS:
        raise ValueError(f"unknown method {method}, expected one of {METHODS}")
    e2_params = e2_params or {}

    pairs = od.pairs.copy()
    pairs[ORIGIN] = pairs[ORIGIN].astype(str)
    pairs[SUPPLY] = pairs[SUPPLY].astype(str)
    supply = supply.copy()
    supply.index = supply.index.astype(str)
    demand = demand.copy()
    demand.index = demand.index.astype(str)

    origins = [str(o) for o in (all_origins if all_origins is not None else od.origins)]

    if pairs.empty:
        return pd.Series(0.0, index=pd.Index(origins, name=ORIGIN), name="access")

    pairs["w"] = _decay_weights(pairs[COST].to_numpy(), od.threshold, method, e2_params)

    if method == "3sfca":
        pairs["m"] = _selection_weights(pairs, supply) * pairs["w"].to_numpy()
    else:
        pairs["m"] = pairs["w"].to_numpy()

    # Step one. R_j = S_j / sum_i m_ij D_i.
    pairs["mD"] = pairs["m"].to_numpy() * demand.reindex(pairs[ORIGIN]).fillna(0.0).to_numpy()
    weighted_demand = pairs.groupby(SUPPLY)["mD"].sum()
    s = supply.reindex(weighted_demand.index).fillna(0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(weighted_demand.to_numpy() > 0, s.to_numpy() / weighted_demand.to_numpy(), 0.0)
    r_j = pd.Series(ratio, index=weighted_demand.index)

    # Step two. A_i = sum_j m_ij R_j.
    pairs["mR"] = pairs["m"].to_numpy() * r_j.reindex(pairs[SUPPLY]).fillna(0.0).to_numpy()
    access = pairs.groupby(ORIGIN)["mR"].sum()

    access = access.reindex(origins).fillna(0.0)
    access.index.name = ORIGIN
    access.name = "access"
    return access


def access_all_methods(
    od: ODStructure,
    supply: pd.Series,
    demand: pd.Series,
    methods: list[str],
    e2_params: dict | None = None,
    all_origins: list[str] | None = None,
) -> pd.DataFrame:
    """Run several methods and return a wide frame, one access column per method."""
    out = {}
    for method in methods:
        out[method] = access_scores(od, supply, demand, method, e2_params, all_origins)
    return pd.DataFrame(out)
