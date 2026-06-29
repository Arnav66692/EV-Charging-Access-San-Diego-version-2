"""Budget-constrained siting integer program.

Selects which candidate sites to build, and at which feasible tier, to maximize
an objective under a per-county port budget. The decision is binary, x_ct is 1 if
candidate c is built at tier t. Constraints, one tier per site, a port budget, and
only feasible candidate tier pairs may be selected. capacity_unknown candidates
have no feasible tier, so they are never selectable.

The objective is linear in the precomputed coefficients, so this is a multiple
choice knapsack, which CBC solves quickly.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pulp


@dataclass(frozen=True)
class SitingResult:
    """Outcome of one optimizer run."""

    selected: pd.DataFrame  # candidate_id, tier, ports
    objective_value: float
    ports_used: int
    status: str
    n_selected: int


def solve_siting(
    coeffs: pd.DataFrame, budget_ports: float, objective: str, time_limit_s: int = 120
) -> SitingResult:
    """Solve the siting IP for one objective and budget.

    coeffs has candidate_id, tier, ports, and the objective columns coef_gap and
    coef_total. objective is gap_closing or total_gain. Returns the selected sites
    and the realized objective and ports used.
    """
    obj_col = {"gap_closing": "coef_gap", "total_gain": "coef_total"}[objective]
    if coeffs.empty:
        return SitingResult(
            coeffs.iloc[0:0][["candidate_id", "tier", "ports"]].copy(),
            0.0, 0, "EMPTY", 0,
        )

    coeffs = coeffs.reset_index(drop=True)
    prob = pulp.LpProblem("siting", pulp.LpMaximize)
    x = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in coeffs.index]

    prob += pulp.lpSum(coeffs.loc[i, obj_col] * x[i] for i in coeffs.index)

    # One tier per site.
    for _, grp in coeffs.groupby("candidate_id"):
        prob += pulp.lpSum(x[i] for i in grp.index) <= 1

    # Port budget.
    prob += pulp.lpSum(int(coeffs.loc[i, "ports"]) * x[i] for i in coeffs.index) <= budget_ports

    prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=time_limit_s))

    chosen = [i for i in coeffs.index if x[i].value() is not None and x[i].value() > 0.5]
    selected = coeffs.loc[chosen, ["candidate_id", "tier", "ports"]].reset_index(drop=True)
    ports_used = int(selected["ports"].sum()) if not selected.empty else 0
    return SitingResult(
        selected=selected,
        objective_value=float(pulp.value(prob.objective) or 0.0),
        ports_used=ports_used,
        status=pulp.LpStatus[prob.status],
        n_selected=int(len(selected)),
    )
