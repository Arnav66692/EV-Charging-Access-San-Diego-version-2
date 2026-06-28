"""SCE DERiM grid layer acquisition.

Pulls the SCE Integration Capacity Analysis load capacity layer from the DERiM
ArcGIS Open Data site through the ArcGIS REST FeatureServer query endpoint. The
endpoint is paginated with resultOffset until the server stops returning more
features. Line section geometry and load capacity MW are captured, from
ica_overall_load. The most_limiting_factor field is captured as the generation
limiting factor, since on this layer it is generation oriented, not a load
limitation. See docs/grid_fields.md. This layer is redistributable.
"""

from __future__ import annotations

import json
from typing import Any, Iterator

import geopandas as gpd
import pandas as pd
import requests

from src.config import Config, load_config
from src.utils import (
    ensure_dir,
    sha256_bytes,
    utc_date,
    utc_now_iso,
    write_gzip_snapshot,
    write_manifest,
)

REQUEST_TIMEOUT_S = 180


def _query_url(cfg: Config) -> str:
    url = cfg["sce_derim"].get("feature_server_url", "")
    if not url:
        raise RuntimeError(
            "sce_derim.feature_server_url is not set in config.yaml. "
            "Set it to the ArcGIS FeatureServer layer query endpoint, "
            "for example https://services.arcgis.com/.../FeatureServer/0/query"
        )
    return url


def paginate_features(
    query_url: str,
    page_size: int,
    out_fields: str = "*",
    session: requests.Session | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield GeoJSON FeatureCollection pages until the server is exhausted.

    ArcGIS signals more pages with exceededTransferLimit. We also stop when a
    page returns no features, which covers servers that omit that flag.
    """
    session = session or requests.Session()
    offset = 0
    while True:
        params = {
            "where": "1=1",
            "outFields": out_fields,
            "outSR": "4326",
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": page_size,
            "returnGeometry": "true",
        }
        response = session.get(query_url, params=params, timeout=REQUEST_TIMEOUT_S)
        response.raise_for_status()
        page = response.json()
        features = page.get("features", [])
        if not features:
            break
        yield page
        if not page.get("properties", {}).get("exceededTransferLimit") and not page.get(
            "exceededTransferLimit"
        ):
            # No explicit more-pages flag and we got a short page, assume done.
            if len(features) < page_size:
                break
        offset += len(features)


def fetch_all(cfg: Config, session: requests.Session | None = None) -> dict[str, Any]:
    """Fetch every page and merge into one GeoJSON FeatureCollection."""
    query_url = _query_url(cfg)
    page_size = int(cfg["sce_derim"]["page_size"])
    out_fields = cfg["sce_derim"]["out_fields"]
    all_features: list[dict[str, Any]] = []
    for page in paginate_features(query_url, page_size, out_fields, session):
        all_features.extend(page.get("features", []))
    return {"type": "FeatureCollection", "features": all_features}


def identify_field(columns: list[str], candidates: list[str]) -> str | None:
    """Return the first candidate present in columns, case insensitive."""
    lower = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    return None


def normalize(gdf: gpd.GeoDataFrame, cfg: Config) -> gpd.GeoDataFrame:
    """Standardise key columns: load_capacity_mw and generation_limiting_factor.

    load_capacity_mw comes from ica_overall_load, the binding minimum ICA load
    value in MW. generation_limiting_factor comes from most_limiting_factor,
    which on this layer is generation oriented, not a load limitation. It is
    carried for context and named honestly. See docs/grid_fields.md.
    """
    cols = list(gdf.columns)
    load_field = identify_field(cols, cfg["sce_derim"]["load_capacity_field_candidates"])
    limit_field = identify_field(
        cols, cfg["sce_derim"]["generation_limiting_field_candidates"]
    )

    out = gdf.copy()
    out["load_capacity_mw"] = (
        pd.to_numeric(out[load_field], errors="coerce") if load_field else pd.NA
    )
    out["generation_limiting_factor"] = out[limit_field] if limit_field else None
    out["grid_source"] = "sce_derim"
    out["source_load_field"] = load_field
    out["source_generation_limiting_field"] = limit_field
    return out


def freeze_snapshot(cfg: Config, geojson: dict[str, Any]) -> dict[str, Any]:
    """Freeze the raw SCE GeoJSON to a dated gzip snapshot with a sha256.

    The SCE layer refreshes monthly, so the pull is frozen for reproducibility,
    the same as AFDC. The snapshot is tracked because this layer is
    redistributable. The sha256 is of the uncompressed content.
    """
    raw_bytes = json.dumps(geojson, separators=(",", ":"), sort_keys=True).encode("utf-8")
    pull_date = utc_date()
    snap_dir = ensure_dir(cfg.path("snapshots"))
    snapshot_path = snap_dir / f"sce_derim_ica_{pull_date}.geojson.gz"
    write_gzip_snapshot(snapshot_path, raw_bytes)

    manifest = {
        "source": "SCE DERiM Integration Capacity Analysis load capacity layer",
        "endpoint": cfg["sce_derim"].get("feature_server_url", ""),
        "query_params": {
            "where": "1=1",
            "outFields": cfg["sce_derim"]["out_fields"],
            "outSR": "4326",
            "f": "geojson",
            "page_size": int(cfg["sce_derim"]["page_size"]),
        },
        "pull_date": pull_date,
        "pulled_at_utc": utc_now_iso(),
        "snapshot_file": snapshot_path.name,
        "row_count": int(len(geojson.get("features", []))),
        "sha256": sha256_bytes(raw_bytes),
        "uncompressed_byte_count": len(raw_bytes),
        "compressed_byte_count": int(snapshot_path.stat().st_size),
        "license": "SCE DERiM Open Data. Redistributable. Attribution to Southern California Edison.",
        "redistributable": True,
        "note": "Frozen for reproducibility. The SCE ICA layer refreshes monthly.",
    }
    write_manifest(
        cfg.path("manifests") / f"sce_derim_ica_{pull_date}.manifest.json", manifest
    )
    return manifest


def run(cfg: Config | None = None) -> gpd.GeoDataFrame:
    """Pull the SCE DERiM layer, freeze it, and write processed/sce_derim_grid.parquet."""
    cfg = cfg or load_config()
    geojson = fetch_all(cfg)

    # Freeze the raw pull first, so the snapshot and sha256 exist before any
    # parsing. The SCE layer refreshes, so results would not reproduce otherwise.
    snap_manifest = freeze_snapshot(cfg, geojson)

    gdf = gpd.GeoDataFrame.from_features(geojson["features"], crs=cfg.crs_storage)
    gdf = normalize(gdf, cfg)

    processed = ensure_dir(cfg.path("processed"))
    out_path = processed / "sce_derim_grid.parquet"
    gdf.to_parquet(out_path)

    manifest = {
        "source": "SCE DERiM Integration Capacity Analysis load capacity layer",
        "endpoint": cfg["sce_derim"].get("feature_server_url", ""),
        "feature_count": int(len(gdf)),
        "load_field": gdf["source_load_field"].iloc[0] if len(gdf) else None,
        "generation_limiting_field": (
            gdf["source_generation_limiting_field"].iloc[0] if len(gdf) else None
        ),
        "snapshot_file": snap_manifest["snapshot_file"],
        "snapshot_sha256": snap_manifest["sha256"],
        "pulled_at_utc": utc_now_iso(),
        "license": "SCE DERiM Open Data. Redistributable. Attribution to Southern California Edison.",
        "redistributable": True,
    }
    write_manifest(cfg.path("manifests") / "sce_derim_grid.manifest.json", manifest)
    print(
        f"SCE DERiM: {len(gdf)} line sections, frozen to {snap_manifest['snapshot_file']} "
        f"sha256 {snap_manifest['sha256'][:12]}..."
    )
    return gdf


if __name__ == "__main__":
    run()
