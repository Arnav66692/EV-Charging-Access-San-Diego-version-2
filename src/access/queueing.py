"""Queueing based supply adjustment, M/M/c.

A charging port is not infinite throughput. A congested site should count for
less than its raw port count suggests. This module computes an M/M/c
availability factor and scales supply by it. The raw port count is preserved
alongside, never overwritten.

The availability factor is the probability that an arriving vehicle finds a free
port, that is one minus the Erlang C probability of waiting. For a fixed arrival
rate per port the factor rises with the number of ports, the pooling gain of a
larger multi server queue.

The queueing inputs are modeled, not measured. There is no station level
utilization data, so arrival and service rates are pre specified assumptions, not
observations. This is a stated limitation. See docs/methods_queueing.md.
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

from src.access.od_types import SUPPLY
from src.config import Config

# Map the SFCA charger type to the config keys for service and arrival rates.
_SERVICE_KEY = {"dcfc": "dcfc", "l2": "l2"}


def erlang_b(c: int, offered_load: float) -> float:
    """Erlang B blocking probability, computed by the stable recursion."""
    b = 1.0
    for k in range(1, c + 1):
        b = (offered_load * b) / (k + offered_load * b)
    return b


def erlang_c(c: int, offered_load: float) -> float:
    """Erlang C probability that an arrival must wait, for c servers.

    offered_load a is in Erlangs, a = arrival_rate / service_rate. Stable for
    a/c < 1. The caller handles the saturated case a/c >= 1 separately.
    """
    rho = offered_load / c
    b = erlang_b(c, offered_load)
    denom = 1.0 - rho + rho * b
    if denom <= 0:
        return 1.0
    return b / denom


def availability_factor(
    ports: int, arrival_rate_per_port: float, service_rate: float
) -> float:
    """Probability an arriving vehicle finds a free port, in (0, 1].

    arrival_rate_per_port and service_rate share the same time unit. Total
    arrival is arrival_rate_per_port times ports, so utilization rho is constant
    in ports, and the factor still rises with ports through the pooling gain.
    When the site is saturated, rho >= 1, the factor is the served fraction
    1/rho, which falls below 1 as it should.
    """
    ports = int(ports)
    if ports <= 0:
        return 0.0
    if arrival_rate_per_port <= 0:
        return 1.0
    if service_rate <= 0:
        return 0.0
    offered_load = arrival_rate_per_port * ports / service_rate
    rho = offered_load / ports
    if rho >= 1.0:
        return 1.0 / rho
    return 1.0 - erlang_c(ports, offered_load)


def queueing_params(cfg: Config, charger_type: str) -> tuple[float, float]:
    """Return arrival_rate_per_port and service_rate, both per hour."""
    q = cfg["access"]["queueing"]
    arrival = float(q["arrival_rate_per_port_per_hour"][_SERVICE_KEY[charger_type]])
    service_minutes = float(q["mean_service_minutes"][_SERVICE_KEY[charger_type]])
    service_rate = 60.0 / service_minutes  # per hour
    return arrival, service_rate


def effective_supply(
    supply_gdf: gpd.GeoDataFrame, charger_type: str, cfg: Config
) -> gpd.GeoDataFrame:
    """Return supply with raw_port_count preserved and capacity scaled.

    When queueing is disabled the availability factor is 1.0 and capacity equals
    the raw port count exactly, which recovers the Phase 2 linear supply. The
    capacity column holds the value the SFCA engine divides demand into.
    """
    out = supply_gdf.copy()
    raw = out["capacity"].astype(float)
    out["raw_port_count"] = raw

    if not cfg["access"]["queueing"].get("enabled", False):
        out["availability_factor"] = 1.0
        out["capacity"] = raw
        return out

    arrival, service_rate = queueing_params(cfg, charger_type)
    factor = raw.map(lambda c: availability_factor(int(round(c)), arrival, service_rate))
    out["availability_factor"] = factor.to_numpy()
    out["capacity"] = (raw * factor).to_numpy()
    return out


def capacity_series_effective(supply_gdf: gpd.GeoDataFrame) -> pd.Series:
    """Effective capacity as a series indexed by supply_id, for the SFCA engine."""
    return pd.Series(
        supply_gdf["capacity"].to_numpy(),
        index=supply_gdf[SUPPLY].astype(str),
        name="capacity",
    )
