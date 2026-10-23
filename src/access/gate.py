"""Euclidean accessibility checks: qualitative pattern or frozen-supply comparison.

A tolerance comparison is not an exact reproduction claim: demographic inputs,
centroids, and algorithm choices also affect the result. Record their hashes.
"""

from __future__ import annotations

import json
import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from src.access.dac_ratio import weighted_median
from src.access.od_cost import EuclideanODProvider, _xy_3310
from src.access.od_types import ORIGIN, SUPPLY
from src.access.sfca import access_scores
from src.access.supply import capacity_series, supply_by_type
from src.acquire.afdc import parse_stations, parse_ports

EPS_METERS = 1.0


@dataclass(frozen=True)
class GateResult:
    """Outcome of the v1-compat gate."""

    path_taken: str
    sfca_dac_ratio: float
    naive_proximity_ratio: float
    passed: bool
    message: str
    details: dict = field(default_factory=dict)


def naive_nearest_distance(
    origins: gpd.GeoDataFrame, supplies: gpd.GeoDataFrame
) -> np.ndarray:
    """Nearest supply distance in meters for each origin, EPSG:3310."""
    origin_xy = _xy_3310(origins)
    supply_xy = _xy_3310(supplies)
    if len(supply_xy) == 0:
        return np.full(len(origin_xy), np.inf)
    tree = cKDTree(supply_xy)
    dist, _ = tree.query(origin_xy, k=1)
    return dist


def _weighted_ratio(
    values: pd.Series, dac: pd.Series, weights: pd.Series
) -> tuple[float, float, float]:
    """Return dac median, non dac median, and their ratio."""
    is_dac = dac == True  # noqa: E712
    dac_med = weighted_median(values[is_dac].to_numpy(), weights[is_dac].to_numpy())
    non_med = weighted_median(values[~is_dac].to_numpy(), weights[~is_dac].to_numpy())
    ratio = dac_med / non_med if non_med and not np.isnan(non_med) and non_med != 0 else float("nan")
    return dac_med, non_med, ratio


def run_gate(
    origins: gpd.GeoDataFrame,
    supplies_dcfc: gpd.GeoDataFrame,
    residential: pd.Series,
    dac_flags: pd.Series,
    population: pd.Series,
    radius_m: float,
    e2_params: dict | None = None,
    v1_snapshot_path: str | Path | None = None,
    v1_reference_ratio: float | None = None,
    tolerance: float = 0.1,
) -> GateResult:
    """Run the v1-compat gate for San Diego and return a documented result.

    origins are geometric centroids for San Diego block groups. supplies_dcfc are
    the DCFC stations. radius_m is the v1 DCFC radius converted to meters.
    """
    if (v1_snapshot_path is None) != (v1_reference_ratio is None):
        raise ValueError("Provide both a frozen AFDC JSON snapshot and reference ratio")
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be finite and non-negative")
    provenance = {"radius_m": radius_m, "method": "g2sfca"}
    if v1_snapshot_path is not None:
        if not math.isfinite(v1_reference_ratio) or v1_reference_ratio <= 0:
            raise ValueError("reference ratio must be positive and finite")
        raw_bytes = Path(v1_snapshot_path).read_bytes()
        raw = json.loads(raw_bytes)
        stations = parse_stations(raw)
        if stations.empty:
            raise ValueError("AFDC snapshot contains no stations")
        stations = stations.loc[
            (stations["status_code"] == "E") & (stations["access_code"] == "public")
        ]
        supplies_dcfc = supply_by_type(parse_ports(raw), stations, "dcfc")
        if supplies_dcfc.empty:
            raise ValueError("AFDC snapshot contains no operating public DCFC supply")
        provenance["snapshot_sha256"] = hashlib.sha256(raw_bytes).hexdigest()
        provenance["snapshot_filter"] = "status_code=E, access_code=public, DCFC"
    # Hash the actual model inputs, not just a filename supplied by the caller.
    origin_rows = pd.DataFrame({ORIGIN: origins[ORIGIN].to_numpy(),
                                "geometry": origins.geometry.to_wkt().to_numpy()})
    for name, value in (("origins", origin_rows), ("residential", residential),
                        ("dac_flags", dac_flags), ("population", population)):
        provenance[name + "_sha256"] = hashlib.sha256(
            value.to_csv().encode("utf-8")
        ).hexdigest()
    provenance["origins_crs"] = str(origins.crs)
    provider = EuclideanODProvider()
    od = provider.od_within_threshold(origins, supplies_dcfc, radius_m)
    supply_series = capacity_series(supplies_dcfc)
    all_origins = origins[ORIGIN].astype(str).tolist()

    access = access_scores(od, supply_series, residential, "g2sfca", e2_params, all_origins)

    frame = pd.DataFrame({"geoid_bg": access.index.astype(str), "access": access.to_numpy()})
    frame["dac"] = frame["geoid_bg"].map(dac_flags.rename(None))
    frame["weight"] = frame["geoid_bg"].map(population.rename(None)).astype(float)

    _, _, sfca_ratio = _weighted_ratio(frame["access"], frame["dac"], frame["weight"])

    # Naive nearest distance proximity. Closer is a higher score. If DAC areas
    # look well served by nearest distance but worse by SFCA, that is the reversal.
    nearest = naive_nearest_distance(origins, supplies_dcfc)
    proximity = pd.Series(1.0 / (nearest + EPS_METERS), index=all_origins)
    frame["proximity"] = frame["geoid_bg"].map(proximity)
    _, _, naive_ratio = _weighted_ratio(frame["proximity"], frame["dac"], frame["weight"])

    if v1_snapshot_path is not None and v1_reference_ratio is not None:
        passed = abs(sfca_ratio - v1_reference_ratio) <= tolerance
        message = (
            f"Frozen-supply compatibility comparison. Recomputed DCFC ratio "
            f"{sfca_ratio:.3f} versus v1 reference {v1_reference_ratio:.3f}, "
            f"tolerance {tolerance}. {'Within' if passed else 'Outside'} tolerance."
        )
        return GateResult(
            path_taken="frozen_supply_comparison",
            sfca_dac_ratio=sfca_ratio,
            naive_proximity_ratio=naive_ratio,
            passed=passed,
            message=message,
            details={**provenance, "v1_reference_ratio": v1_reference_ratio, "tolerance": tolerance},
        )

    # Qualitative path. DCFC ratio below 1, and a reversal where naive nearest
    # distance is more favorable to DAC than SFCA is.
    ratio_below_one = sfca_ratio < 1.0
    reversal = naive_ratio > sfca_ratio
    passed = bool(ratio_below_one and reversal)
    message = (
        "Qualitative pattern path. Exact reproduction requires v1's frozen AFDC "
        "snapshot, which was not provided, so the station set differs. "
        f"SFCA DAC ratio {sfca_ratio:.3f}, below 1 is {ratio_below_one}. "
        f"Naive proximity ratio {naive_ratio:.3f}. Reversal, naive more favorable "
        f"to DAC than SFCA, is {reversal}."
    )
    return GateResult(
        path_taken="qualitative_pattern",
        sfca_dac_ratio=sfca_ratio,
        naive_proximity_ratio=naive_ratio,
        passed=passed,
        message=message,
        details={**provenance, "ratio_below_one": ratio_below_one, "reversal": reversal},
    )


def write_gate_result(path: Path, result: GateResult) -> Path:
    """Write the gate result to JSON for the record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "path_taken": result.path_taken,
        "sfca_dac_ratio": result.sfca_dac_ratio,
        "naive_proximity_ratio": result.naive_proximity_ratio,
        "passed": result.passed,
        "message": result.message,
        "details": result.details,
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path
