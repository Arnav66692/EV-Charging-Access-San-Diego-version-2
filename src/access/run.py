"""Accessibility run orchestration.

Two entry points wire the engine to the Phase 1 processed outputs.

run_v1_gate runs the v1-compat gate for San Diego with the euclidean backend. It
needs no Docker. It needs the Phase 1 processed AFDC, ACS, and CES tables, plus
the population weighted centroids.

run_primary runs the full primary surfaces with the OSRM backend. It needs a live
OSRM instance, which needs Docker. It is wired and ready, and waits on that
instance.

Both raise a clear error when an input is missing.
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

from src.access.centroids import population_weighted_centroids
from src.access.dac_ratio import dac_access_ratio
from src.access.demand import lodes_wac_demand, residential_from_acs
from src.access.gate import GateResult, run_gate, write_gate_result
from src.access.od_cost import EuclideanODProvider, OSRMODProvider
from src.access.scores import (
    DEFAULT_TYPE_SPECS,
    compute_surfaces,
    config_hash,
    county_to_territory,
    snapshot_provenance,
    write_surfaces,
)
from src.access.supply import supply_by_type
from src.config import Config, fips, load_config
from src.utils import MILES_TO_METERS

MILE_M = MILES_TO_METERS


def _require(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Missing required input {path}. Run the Phase 1 acquisition steps "
            f"first, and the Phase 2 data layers, make access-centroids and "
            f"make access-lodes."
        )
    return path


def _load_supplies(cfg: Config) -> dict[str, gpd.GeoDataFrame]:
    processed = cfg.path("processed")
    stations = pd.read_parquet(_require(processed / "afdc_stations.parquet"))
    ports = pd.read_parquet(_require(processed / "afdc_ports.parquet"))
    return {
        "dcfc": supply_by_type(ports, stations, "dcfc"),
        "l2": supply_by_type(ports, stations, "l2"),
    }


def _load_demand(cfg: Config) -> dict[str, pd.Series]:
    processed = cfg.path("processed")
    acs = pd.read_parquet(_require(processed / "acs_blockgroups.parquet"))
    return {
        "residential": residential_from_acs(acs),
        "lodes_wac": lodes_wac_demand(cfg),
    }


def run_v1_gate(cfg: Config | None = None) -> GateResult:
    """Run the v1-compat gate for San Diego and write the result."""
    cfg = cfg or load_config()
    processed = cfg.path("processed")

    centroids = population_weighted_centroids(cfg)
    san_diego = {fips(c) for c in cfg.territory_counties("sdge")}
    origins = centroids[centroids["geoid_bg"].str[:5].isin(san_diego)].copy()

    supplies = _load_supplies(cfg)["dcfc"]

    acs = pd.read_parquet(_require(processed / "acs_blockgroups.parquet"))
    residential = residential_from_acs(acs)
    population = residential

    ces = pd.read_parquet(_require(processed / "ces_dac_blockgroups.parquet"))
    dac_flags = pd.Series(
        ces["dac_flag"].to_numpy(), index=ces["geoid_bg"].astype(str), dtype="boolean"
    )

    radius_m = float(cfg["access"]["thresholds"]["euclidean_miles"]["dcfc"]) * MILE_M
    e2 = cfg["access"]["sfca"]["e2sfca"]

    result = run_gate(
        origins=origins,
        supplies_dcfc=supplies,
        residential=residential,
        dac_flags=dac_flags,
        population=population,
        radius_m=radius_m,
        e2_params=e2,
    )
    write_gate_result(cfg.path("manifests") / "access_v1_gate.json", result)
    print(result.message)
    return result


def run_primary(cfg: Config | None = None) -> pd.DataFrame:
    """Run the primary drive time surfaces. Needs a live OSRM instance."""
    from src.routing.osrm_client import OSRMClient

    cfg = cfg or load_config()
    centroids = population_weighted_centroids(cfg)
    supplies = _load_supplies(cfg)
    demand = _load_demand(cfg)

    provider = OSRMODProvider(
        table_fn=OSRMClient().table,
        upper_bound_speed_mph=float(cfg["access"]["prefilter"]["upper_bound_speed_mph"]),
    )
    thresholds = {
        "dcfc": float(cfg["access"]["thresholds"]["drive_time_minutes"]["dcfc"]),
        "l2": float(cfg["access"]["thresholds"]["drive_time_minutes"]["l2"]),
    }
    provenance = snapshot_provenance(cfg)
    provenance["config_hash"] = config_hash(cfg)

    surfaces = compute_surfaces(
        origins=centroids,
        supplies_by_type=supplies,
        demand_by_spec=demand,
        provider=provider,
        thresholds_by_type=thresholds,
        methods=cfg["access"]["sfca"]["methods"],
        county_to_territory=county_to_territory(cfg),
        e2_params=cfg["access"]["sfca"]["e2sfca"],
        type_specs=DEFAULT_TYPE_SPECS,
        provenance=provenance,
        mode="drive_time",
    )
    write_surfaces(cfg, surfaces, "primary_drive_time")

    ces = pd.read_parquet(cfg.path("processed") / "ces_dac_blockgroups.parquet")
    dac_flags = pd.Series(
        ces["dac_flag"].to_numpy(), index=ces["geoid_bg"].astype(str), dtype="boolean"
    )
    acs = pd.read_parquet(cfg.path("processed") / "acs_blockgroups.parquet")
    population = residential_from_acs(acs)
    ratios = dac_access_ratio(surfaces, dac_flags, population)
    ratios.to_parquet(cfg.path("processed") / "dac_access_ratio_primary.parquet", index=False)
    print(f"Primary surfaces: {len(surfaces)} rows. DAC ratios:\n{ratios}")
    return surfaces


if __name__ == "__main__":
    run_v1_gate()
