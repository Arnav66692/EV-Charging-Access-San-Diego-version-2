"""Marginal access coefficients for the siting optimizer.

The optimizer is an integer program, so the access gain from building a site must
be linear in the decision. The standard 2SFCA linearization gives that. A new
DCFC site at candidate c with s ports adds, to each block group i in its
catchment, an access increment

    delta_i = w_ic * R_c,   R_c = s / sum_k w_kc pop_k

where w is the Gaussian decay and the sum runs over block groups in the
catchment. This is additive across sites, which ignores competition among the new
sites, the usual and conservative siting approximation. See
docs/methods_optimizer.md.

Two objective coefficients are precomputed per candidate and tier.

  gap closing. The population weighted access gain in DAC block groups,
    sum_{i in DAC} pop_i delta_i. Raising DAC area access closes the gap. This is
    a linear surrogate for raising the DAC median.
  total gain. The equity weighted total access gain,
    sum_i weight_i pop_i delta_i, with a heavier weight on DAC areas.

Both scale linearly with the tier port count, so a candidate's value per port is
the same across tiers, and the tier choice is driven by feasibility and budget.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from src.access.decay import gaussian_g2sfca
from src.access.od_cost import _xy_3310

TIERS = ("small", "medium", "large")


def candidate_coefficients(
    centroids: gpd.GeoDataFrame,
    candidates: gpd.GeoDataFrame,
    feasibility: pd.DataFrame,
    population: pd.Series,
    dac_flags: pd.Series,
    d0_m: float,
    tier_ports: dict[str, int],
    equity_weight_dac: float,
) -> pd.DataFrame:
    """Per candidate and feasible tier, the objective coefficients for the IP.

    centroids has geoid_bg and point geometry. candidates has candidate_id and
    point geometry. feasibility has candidate_id, capacity_unknown, and a nullable
    feasible_<tier> per tier. Returns candidate_id, tier, ports, coef_gap,
    coef_total. A capacity_unknown candidate yields no rows, it is not selectable.
    """
    bg_xy = _xy_3310(centroids)
    bg_ids = centroids["geoid_bg"].astype(str).to_numpy()
    pop = population.reindex(bg_ids).fillna(0.0).to_numpy().astype("float64")
    isdac = dac_flags.reindex(bg_ids).fillna(False).astype(bool).to_numpy()
    eqw = np.where(isdac, float(equity_weight_dac), 1.0)

    cand_xy = _xy_3310(candidates)
    cand_ids = candidates["candidate_id"].astype(str).to_numpy()

    # Coerce the nullable boolean flags to plain bools, NA becomes False, so the
    # truth tests below are unambiguous. A numpy or pandas boolean is not the
    # Python True singleton, so an identity test would silently fail.
    feas = feasibility.copy()
    feas["candidate_id"] = feas["candidate_id"].astype(str)
    feas["capacity_unknown"] = feas["capacity_unknown"].fillna(True).astype(bool)
    for tier in TIERS:
        col = f"feasible_{tier}"
        if col in feas.columns:
            feas[col] = feas[col].fillna(False).astype(bool)
    feas = feas.drop_duplicates("candidate_id").set_index("candidate_id")

    tree = cKDTree(bg_xy)
    neighbor_lists = tree.query_ball_point(cand_xy, r=d0_m)

    rows = []
    for ci, idxs in enumerate(neighbor_lists):
        cid = cand_ids[ci]
        if cid not in feas.index or not idxs:
            continue
        frow = feas.loc[cid]
        if bool(frow.get("capacity_unknown", True)):
            continue
        idx = np.asarray(idxs)
        dist = np.linalg.norm(bg_xy[idx] - cand_xy[ci], axis=1)
        w = gaussian_g2sfca(dist, d0_m)
        demand = float((w * pop[idx]).sum())
        if demand <= 0:
            continue
        # Per-port value densities. Multiply by ports for the tier coefficient.
        dac_density = float((pop[idx] * w * isdac[idx]).sum()) / demand
        total_density = float((eqw[idx] * pop[idx] * w).sum()) / demand

        for tier in TIERS:
            if not bool(frow.get(f"feasible_{tier}", False)):
                continue
            ports = int(tier_ports[tier])
            rows.append(
                {
                    "candidate_id": cid,
                    "tier": tier,
                    "ports": ports,
                    "coef_gap": dac_density * ports,
                    "coef_total": total_density * ports,
                }
            )
    return pd.DataFrame(
        rows, columns=["candidate_id", "tier", "ports", "coef_gap", "coef_total"]
    )


def portfolio_delta_access(
    selected: pd.DataFrame,
    centroids: gpd.GeoDataFrame,
    candidates: gpd.GeoDataFrame,
    population: pd.Series,
    d0_m: float,
    tier_ports: dict[str, int],
) -> pd.Series:
    """Additive access increment per block group from a selected portfolio.

    selected has candidate_id and tier. Returns a Series indexed by geoid_bg of
    the summed marginal access from all selected sites, the same 2SFCA additive
    model the optimizer maximizes. Used to evaluate the realized gain and to
    bootstrap it, holding the portfolio fixed.
    """
    bg_xy = _xy_3310(centroids)
    bg_ids = centroids["geoid_bg"].astype(str).to_numpy()
    pop = population.reindex(bg_ids).fillna(0.0).to_numpy().astype("float64")
    delta = np.zeros(len(bg_ids), dtype="float64")
    if selected.empty:
        return pd.Series(delta, index=pd.Index(bg_ids, name="geoid_bg"))

    cand = candidates.copy()
    cand["candidate_id"] = cand["candidate_id"].astype(str)
    cand_xy_all = {cid: xy for cid, xy in zip(cand["candidate_id"], _xy_3310(cand))}
    tree = cKDTree(bg_xy)

    for _, row in selected.iterrows():
        cid = str(row["candidate_id"])
        if cid not in cand_xy_all:
            continue
        cxy = cand_xy_all[cid]
        idx = np.asarray(tree.query_ball_point(cxy, r=d0_m))
        if idx.size == 0:
            continue
        dist = np.linalg.norm(bg_xy[idx] - cxy, axis=1)
        w = gaussian_g2sfca(dist, d0_m)
        demand = float((w * pop[idx]).sum())
        if demand <= 0:
            continue
        ratio = int(tier_ports[row["tier"]]) / demand
        delta[idx] += w * ratio
    return pd.Series(delta, index=pd.Index(bg_ids, name="geoid_bg"))
