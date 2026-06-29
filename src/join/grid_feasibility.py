"""Grid feasibility join. Classify candidate sites by the fast-charging build the
local grid can host, from the frozen SCE ICA load capacity layer.

For each candidate already joined to its nearest SCE line section, read that
section's ica_overall_load headroom in MW and classify feasibility at each site
size tier. SCE only, since the SDG&E layer is not in hand.

Honest redaction handling. SCE applies a 15/15 redaction, so some sections have
no published capacity. A candidate joined to a redacted or null capacity section,
or with no section within the snap threshold, is flagged capacity_unknown. It is
never silently treated as feasible or infeasible.

Screening level only. This is ICA most limiting hour headroom, not an
interconnection guarantee. Upgrades may still be required. Verbatim SCE caveat,
see docs/grid_fields.md. "While Southern California Edison makes every effort to
ensure the accuracy of DRPEP, the data provided is for information purposes only.
Southern California Edison makes no guarantee, expressly or implied, for the
outcome of an interconnection request."
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

from src.config import Config, load_config
from src.utils import ensure_dir, utc_now_iso, write_manifest

SCE_SCREENING_CAVEAT = (
    "While Southern California Edison makes every effort to ensure the accuracy of "
    "DRPEP, the data provided is for information purposes only. Southern California "
    "Edison makes no guarantee, expressly or implied, for the outcome of an "
    "interconnection request."
)


def tier_requirements(cfg: Config) -> dict[str, float]:
    """Required load headroom in MW per tier, ports times kW times diversity."""
    gf = cfg["grid_feasibility"]
    diversity = float(gf["diversity_factor"])
    out = {}
    for tier, spec in gf["tiers"].items():
        out[tier] = float(spec["ports"]) * float(spec["kw_per_port"]) * diversity / 1000.0
    return out


def classify_feasibility(
    joined: pd.DataFrame, tiers: dict[str, float]
) -> pd.DataFrame:
    """Classify each candidate by tier feasibility, with honest unknown handling.

    joined needs candidate_id, joined_flag, and load_capacity_mw. Returns one row
    per input candidate with section_mw, capacity_unknown, grid_status, and a
    feasible_<tier> nullable boolean per tier. Rows are conserved.
    """
    df = joined.copy()
    section_mw = pd.to_numeric(df["load_capacity_mw"], errors="coerce")
    joined_flag = df["joined_flag"].astype("boolean").fillna(False)
    capacity_known = joined_flag & section_mw.notna()

    out = pd.DataFrame(
        {
            "candidate_id": df["candidate_id"].astype(str).to_numpy(),
            "county_fips": df["county_fips"].astype(str).to_numpy()
            if "county_fips" in df.columns
            else None,
            "section_mw": section_mw.to_numpy(),
            "capacity_unknown": (~capacity_known).to_numpy(),
        }
    )

    # Grid status reason, so the unknown bucket is not opaque.
    status = pd.Series("feasible_classified", index=out.index, dtype="object")
    status[~joined_flag.to_numpy()] = "no_section_within_threshold"
    status[(joined_flag & section_mw.isna()).to_numpy()] = "capacity_redacted"
    out["grid_status"] = status.to_numpy()

    # Tier feasibility. Nullable boolean, NA where capacity is unknown, so an
    # unknown is never marked feasible or infeasible.
    for tier, required in tiers.items():
        col = pd.array([pd.NA] * len(out), dtype="boolean")
        known_mask = capacity_known.to_numpy()
        col[known_mask] = section_mw.to_numpy()[known_mask] >= required
        out[f"feasible_{tier}"] = col

    if len(out) != len(joined):
        raise ValueError(
            f"grid feasibility join changed row count: {len(joined)} in, {len(out)} out"
        )
    return out


def run(cfg: Config | None = None) -> pd.DataFrame:
    """Classify SCE-territory candidates by grid feasibility tier.

    Reads data/processed/joined_candidates_sce.parquet, writes
    data/processed/grid_feasibility_sce.parquet and a manifest.
    """
    cfg = cfg or load_config()
    processed = ensure_dir(cfg.path("processed"))
    joined = gpd.read_parquet(processed / "joined_candidates_sce.parquet")
    tiers = tier_requirements(cfg)

    feasibility = classify_feasibility(joined, tiers)
    feasibility.to_parquet(processed / "grid_feasibility_sce.parquet", index=False)

    counts = {
        "candidates": int(len(feasibility)),
        "capacity_unknown": int(feasibility["capacity_unknown"].sum()),
        "grid_status": feasibility["grid_status"].value_counts().to_dict(),
    }
    for tier in tiers:
        counts[f"feasible_{tier}"] = int((feasibility[f"feasible_{tier}"] == True).sum())  # noqa: E712

    manifest = {
        "source": "SCE ICA load capacity, frozen snapshot, joined to OSM candidates",
        "tier_requirements_mw": tiers,
        "diversity_factor": float(cfg["grid_feasibility"]["diversity_factor"]),
        "screening_caveat": SCE_SCREENING_CAVEAT,
        "counts": counts,
        "ran_at_utc": utc_now_iso(),
        "note": "Screening level ICA headroom, not an interconnection guarantee. "
        "SDG&E territory excluded, layer not in hand.",
        "redistributable": True,
    }
    write_manifest(cfg.path("manifests") / "grid_feasibility_sce.manifest.json", manifest)
    print(f"Grid feasibility: {counts}")
    return feasibility


if __name__ == "__main__":
    run()
