"""Candidate site to grid line section join.

For each candidate site, find the nearest grid line section within a configurable
threshold, in EPSG:3310 where distances are meters. The load capacity MW of the
matched section is carried onto the candidate. The join is run separately per
utility territory so each candidate is matched only against the grid that serves
its county.

Every candidate is accounted for. A candidate either joins to a section within
the threshold, with joined_flag True, or it is explicitly flagged unjoined,
joined_flag False. There is never a silent drop.

Licensing note. The SCE joined table is redistributable. The SDG&E joined table
carries load capacity values derived from an input only layer, so it is written
to a gitignored interim path. A redistributable SDG&E feasibility table that
omits the raw MW value is written to processed.
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

from src.config import Config, fips, load_config
from src.utils import ensure_dir, utc_now_iso, write_manifest

SNAP_DISTANCE_COL = "snap_distance_m"
CARRY_COLS = ["load_capacity_mw", "generation_limiting_factor"]


def county_to_territory(cfg: Config) -> dict[str, str]:
    """Map each in-scope county FIPS to its utility territory name."""
    mapping: dict[str, str] = {}
    for territory, spec in cfg["territories"].items():
        for county in spec["counties"]:
            mapping[fips(county)] = territory
    return mapping


def nearest_join_within(
    candidates: gpd.GeoDataFrame,
    grid: gpd.GeoDataFrame,
    max_distance_m: float,
    working_crs: str,
    storage_crs: str,
) -> gpd.GeoDataFrame:
    """Nearest join candidates to grid within max_distance_m, in the working CRS.

    Returns the candidates with snap_distance_m, the carried grid attributes, and
    a joined_flag boolean. Geometry is returned in the storage CRS. No candidate
    is dropped. Ties are broken by the smallest snap distance.
    """
    if candidates.empty:
        out = candidates.copy()
        out[SNAP_DISTANCE_COL] = pd.Series(dtype="float64")
        out["joined_flag"] = pd.Series(dtype="bool")
        for col in CARRY_COLS:
            out[col] = pd.NA
        return out

    cand_work = candidates.to_crs(working_crs).copy()
    cand_work["_cand_row"] = range(len(cand_work))

    right_cols = ["geometry"] + [c for c in CARRY_COLS if c in grid.columns]
    grid_work = grid.to_crs(working_crs)[right_cols].copy()

    if grid_work.empty:
        joined = cand_work.copy()
        joined[SNAP_DISTANCE_COL] = pd.NA
        for col in CARRY_COLS:
            joined[col] = pd.NA
    else:
        joined = gpd.sjoin_nearest(
            cand_work,
            grid_work,
            how="left",
            max_distance=max_distance_m,
            distance_col=SNAP_DISTANCE_COL,
        )
        # sjoin_nearest can emit multiple rows per candidate on ties. Keep the
        # nearest, breaking remaining ties deterministically by row order.
        joined = (
            joined.sort_values([SNAP_DISTANCE_COL], na_position="last")
            .drop_duplicates(subset="_cand_row", keep="first")
            .sort_values("_cand_row")
        )

    joined["joined_flag"] = joined[SNAP_DISTANCE_COL].notna()
    for col in CARRY_COLS:
        if col not in joined.columns:
            joined[col] = pd.NA
    # A candidate that did not join must carry no capacity value.
    joined.loc[~joined["joined_flag"], CARRY_COLS] = pd.NA

    drop_cols = [c for c in ("index_right", "_cand_row") if c in joined.columns]
    joined = joined.drop(columns=drop_cols)
    result = gpd.GeoDataFrame(joined, geometry="geometry", crs=working_crs).to_crs(
        storage_crs
    )
    return result.reset_index(drop=True)


def run_territory(
    cfg: Config,
    territory: str,
    candidates: gpd.GeoDataFrame,
    grid: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Filter candidates to the territory counties and join to its grid."""
    counties = set(cfg.territory_counties(territory))
    in_territory = candidates[candidates["county_fips"].isin(counties)].copy()
    max_distance = float(cfg["join"]["max_snap_distance_m"])
    joined = nearest_join_within(
        in_territory, grid, max_distance, cfg.crs_working, cfg.crs_storage
    )
    joined["territory"] = territory
    return joined


def run(cfg: Config | None = None) -> dict[str, int]:
    """Run both territory joins and write per-territory outputs.

    Reads:
      data/processed/candidate_sites.parquet
      data/processed/sce_derim_grid.parquet
      data/interim/sdge_ica_grid.parquet      gitignored, input only
    Writes:
      data/processed/joined_candidates_sce.parquet         redistributable
      data/interim/joined_candidates_sdge.parquet          gitignored, has MW
      data/processed/sdge_candidate_feasibility.parquet    redistributable flags
    """
    cfg = cfg or load_config()
    processed = ensure_dir(cfg.path("processed"))
    interim = ensure_dir(cfg.path("interim"))

    candidates = gpd.read_parquet(processed / "candidate_sites.parquet")

    counts: dict[str, int] = {}

    # SCE territory, redistributable end to end.
    sce_grid = gpd.read_parquet(processed / "sce_derim_grid.parquet")
    sce_joined = run_territory(cfg, "sce", candidates, sce_grid)
    sce_joined.to_parquet(processed / "joined_candidates_sce.parquet")
    counts["sce_total"] = int(len(sce_joined))
    counts["sce_joined"] = int(sce_joined["joined_flag"].sum())
    counts["sce_unjoined"] = int((~sce_joined["joined_flag"]).sum())

    # SDG&E territory, input only. Full table with MW stays in gitignored interim.
    sdge_grid = gpd.read_parquet(interim / "sdge_ica_grid.parquet")
    sdge_joined = run_territory(cfg, "sdge", candidates, sdge_grid)
    sdge_joined.to_parquet(interim / "joined_candidates_sdge.parquet")

    # Redistributable feasibility view. No raw MW, just the derived flags.
    feasibility = sdge_joined[
        ["candidate_id", "county_fips", "territory", "joined_flag", SNAP_DISTANCE_COL]
    ].copy()
    feasibility["has_grid_within_threshold"] = feasibility["joined_flag"]
    feasibility = feasibility.drop(columns=["joined_flag"])
    feasibility.to_parquet(processed / "sdge_candidate_feasibility.parquet", index=False)

    counts["sdge_total"] = int(len(sdge_joined))
    counts["sdge_joined"] = int(sdge_joined["joined_flag"].sum())
    counts["sdge_unjoined"] = int((~sdge_joined["joined_flag"]).sum())

    manifest = {
        "join_max_snap_distance_m": float(cfg["join"]["max_snap_distance_m"]),
        "working_crs": cfg.crs_working,
        "counts": counts,
        "ran_at_utc": utc_now_iso(),
        "note": "SDG&E joined table with MW is gitignored. Feasibility flags are shareable.",
    }
    write_manifest(cfg.path("manifests") / "candidate_grid_join.manifest.json", manifest)
    print(f"Join counts: {counts}")
    return counts


if __name__ == "__main__":
    run()
