"""SDG&E ICA grid layer acquisition. Input only, not redistributable.

The SDG&E Integration Capacity Analysis map is gated behind a free SDG&E
account. The user downloads the layer and drops it at a known path, or points
SDGE_ICA_PATH at it. This module reads that file, parses line section geometry
and load capacity MW, and writes a derived grid to a gitignored interim path.

The raw layer and its derived geometry are never committed. Only feasibility
flags derived downstream are redistributable. See LICENSING.md.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from src.acquire.sce_derim import identify_field
from src.config import Config, load_config
from src.utils import ensure_dir, utc_now_iso, write_manifest

REDISTRIBUTABLE = False


def resolve_raw_path(cfg: Config) -> Path:
    """Resolve the SDG&E raw file path from the env var or the configured default."""
    env_var = cfg["sdge_ica"]["raw_path_env"]
    override = cfg.secret(env_var)
    if override:
        return Path(override).expanduser().resolve()
    return (cfg.root / cfg["sdge_ica"]["raw_path"]).resolve()


def load(cfg: Config) -> gpd.GeoDataFrame:
    """Read the user-provided SDG&E file. Supports any format geopandas reads."""
    path = resolve_raw_path(cfg)
    if not path.exists():
        raise FileNotFoundError(
            f"SDG&E ICA file not found at {path}. Download it from the SDG&E ICA "
            f"map with a free account and drop it there, or set the "
            f"{cfg['sdge_ica']['raw_path_env']} env var. See README."
        )
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs(cfg.crs_storage)
    else:
        gdf = gdf.to_crs(cfg.crs_storage)
    return gdf


def normalize(gdf: gpd.GeoDataFrame, cfg: Config) -> gpd.GeoDataFrame:
    """Standardise the load capacity column and tag the source."""
    load_field = identify_field(
        list(gdf.columns), cfg["sdge_ica"]["load_capacity_field_candidates"]
    )
    out = gdf.copy()
    out["load_capacity_mw"] = (
        pd.to_numeric(out[load_field], errors="coerce") if load_field else pd.NA
    )
    out["grid_source"] = "sdge_ica"
    out["source_load_field"] = load_field
    out["redistributable"] = REDISTRIBUTABLE
    return out


def run(cfg: Config | None = None) -> gpd.GeoDataFrame:
    """Read and normalise SDG&E, writing to a gitignored interim parquet.

    Output goes to data/interim, which is gitignored, because the SDG&E geometry
    is input only. Downstream feasibility flags may be redistributed, the
    geometry may not.
    """
    cfg = cfg or load_config()
    gdf = normalize(load(cfg), cfg)

    interim = ensure_dir(cfg.path("interim"))
    out_path = interim / "sdge_ica_grid.parquet"
    gdf.to_parquet(out_path)

    manifest = {
        "source": "SDG&E Integration Capacity Analysis load capacity layer",
        "input_path": str(resolve_raw_path(cfg)),
        "feature_count": int(len(gdf)),
        "load_field": gdf["source_load_field"].iloc[0] if len(gdf) else None,
        "read_at_utc": utc_now_iso(),
        "license": "SDG&E ICA map. Input only. NOT redistributable. Gated behind a free account.",
        "redistributable": False,
        "note": "Raw and derived geometry stay gitignored. Only feasibility flags are shareable.",
    }
    write_manifest(cfg.path("manifests") / "sdge_ica_grid.manifest.json", manifest)
    print(f"SDG&E ICA: {len(gdf)} line sections read, written to gitignored interim")
    return gdf


if __name__ == "__main__":
    run()
