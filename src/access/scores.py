"""Access score orchestration.

Computes per block group access for each territory, charger type, method, and
demand spec, then tags every row with the AFDC snapshot it was computed from,
the run mode, and a config hash. The surfaces move whenever the inputs move, so
the provenance is recorded on every row.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

from src.access.od_cost import ODCostProvider
from src.access.od_types import ORIGIN
from src.access.sfca import access_scores
from src.access.supply import capacity_series
from src.config import Config, fips, load_config
from src.utils import read_manifest

# Which demand specs feed each charger type.
DEFAULT_TYPE_SPECS = {"dcfc": ["residential", "lodes_wac"], "l2": ["residential"]}


def config_hash(cfg: Config) -> str:
    """Stable short hash of the accessibility relevant config."""
    payload = {
        "access": cfg["access"],
        "lodes": cfg.get("lodes"),
        "crs": cfg["crs"],
        "counties": cfg["counties"],
    }
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def snapshot_provenance(cfg: Config) -> dict[str, str]:
    """Find the AFDC snapshot id and sha256 the access run is computed from.

    Prefers the most recent dated AFDC manifest. Falls back to the committed
    sample manifest so fixture runs still record a provenance.
    """
    manifests = sorted(cfg.path("manifests").glob("afdc_ca_elec_*.manifest.json"))
    dated = [m for m in manifests if "sample" not in m.name]
    chosen = dated[-1] if dated else (manifests[-1] if manifests else None)
    if chosen is None:
        return {"snapshot_file": "unknown", "snapshot_sha256": "unknown"}
    manifest = read_manifest(chosen)
    return {
        "snapshot_file": manifest.get("snapshot_file", "unknown"),
        "snapshot_sha256": manifest.get("sha256", "unknown"),
    }


def territory_of(geoid_bg: str, county_to_territory: dict[str, str]) -> str | None:
    return county_to_territory.get(geoid_bg[:5])


def compute_surfaces(
    origins: gpd.GeoDataFrame,
    supplies_by_type: dict[str, gpd.GeoDataFrame],
    demand_by_spec: dict[str, pd.Series],
    provider: ODCostProvider,
    thresholds_by_type: dict[str, float],
    methods: list[str],
    county_to_territory: dict[str, str],
    e2_params: dict | None = None,
    type_specs: dict[str, list[str]] | None = None,
    provenance: dict[str, str] | None = None,
    mode: str = "drive_time",
) -> pd.DataFrame:
    """Compute tidy long access scores across all reporting dimensions.

    This is pure given its inputs. It does no IO and needs no live OSRM. The
    provider is injected, so a mock or the euclidean backend drives the tests.
    """
    type_specs = type_specs or DEFAULT_TYPE_SPECS
    provenance = provenance or {}
    all_origins = origins[ORIGIN].astype(str).tolist()
    territory = {g: territory_of(g, county_to_territory) for g in all_origins}

    frames = []
    for charger_type, supplies in supplies_by_type.items():
        od = provider.od_within_threshold(
            origins[[ORIGIN, "geometry"]], supplies, thresholds_by_type[charger_type]
        )
        supply_series = capacity_series(supplies)
        for spec in type_specs.get(charger_type, []):
            demand = demand_by_spec[spec]
            for method in methods:
                access = access_scores(
                    od, supply_series, demand, method, e2_params, all_origins
                )
                frame = access.reset_index()
                frame.columns = ["geoid_bg", "access"]
                frame["territory"] = frame["geoid_bg"].map(territory)
                frame["charger_type"] = charger_type
                frame["method"] = method
                frame["demand_spec"] = spec
                frames.append(frame)

    out = pd.concat(frames, ignore_index=True)
    out["mode"] = mode
    out["snapshot_file"] = provenance.get("snapshot_file", "unknown")
    out["snapshot_sha256"] = provenance.get("snapshot_sha256", "unknown")
    out["config_hash"] = provenance.get("config_hash", "unknown")
    # Drop origins that fall outside the in-scope territories.
    return out[out["territory"].notna()].reset_index(drop=True)


def write_surfaces(cfg: Config, surfaces: pd.DataFrame, name: str) -> Path:
    """Write a tidy access surface table to processed, keyed to the snapshot."""
    processed = cfg.path("processed")
    processed.mkdir(parents=True, exist_ok=True)
    out_path = processed / f"access_{name}.parquet"
    surfaces.to_parquet(out_path, index=False)
    return out_path


def county_to_territory(cfg: Config) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for territory, spec in cfg["territories"].items():
        for county in spec["counties"]:
            mapping[fips(county)] = territory
    return mapping
