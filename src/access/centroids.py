"""Block group centroids, in two modes.

population_weighted uses the 2020 block group centers of population file, the
same source family located in Phase 1. It is the primary mode. It places the
centroid where people actually are, not at the geometric middle of the polygon.

geometric uses the polygon centroid. It is kept only for the v1-compat gate,
which compares with v1, which used geometric centroids.

All centroids are returned as points in EPSG:4326. FIPS identifiers are strings.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.geometry import Point

from src.access.od_types import ORIGIN
from src.config import Config, fips, load_config

REQUEST_TIMEOUT_S = 120


def parse_centers_of_population(lines: Iterable[str]) -> pd.DataFrame:
    """Parse the centers of population CSV into geoid_bg, population, lat, lon.

    Columns are STATEFP, COUNTYFP, TRACTCE, BLKGRPCE, POPULATION, LATITUDE,
    LONGITUDE. The first line is a header. Latitude carries a leading sign.
    """
    text = "".join(lines) if not isinstance(lines, str) else lines
    # The Census file carries a UTF-8 byte order mark on the header. Strip it so
    # the first column name is STATEFP, not a BOM-prefixed variant.
    text = text.lstrip("﻿")
    df = pd.read_csv(
        io.StringIO(text.encode("utf-8").decode("utf-8-sig")),
        dtype={
            "STATEFP": str,
            "COUNTYFP": str,
            "TRACTCE": str,
            "BLKGRPCE": str,
        },
    )
    geoid = (
        df["STATEFP"].str.zfill(2)
        + df["COUNTYFP"].str.zfill(3)
        + df["TRACTCE"].str.zfill(6)
        + df["BLKGRPCE"].str.zfill(1)
    )
    return pd.DataFrame(
        {
            "geoid_bg": geoid,
            "population": pd.to_numeric(df["POPULATION"], errors="coerce").fillna(0).astype(int),
            "lat": pd.to_numeric(df["LATITUDE"], errors="coerce"),
            "lon": pd.to_numeric(df["LONGITUDE"], errors="coerce"),
        }
    )


def centers_to_geodataframe(df: pd.DataFrame, counties: set[str] | None = None) -> gpd.GeoDataFrame:
    """Build a point GeoDataFrame from a parsed centers table, EPSG:4326."""
    if counties is not None:
        df = df[df["geoid_bg"].str[:5].isin(counties)].copy()
    geometry = [Point(lon, lat) for lon, lat in zip(df["lon"], df["lat"])]
    gdf = gpd.GeoDataFrame(
        df.assign(**{ORIGIN: df["geoid_bg"].astype(str)}),
        geometry=geometry,
        crs="EPSG:4326",
    )
    return gdf[[ORIGIN, "geoid_bg", "population", "geometry"]]


def geometric_centroids(block_group_polygons: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Polygon centroids for the v1-compat gate.

    Centroids are computed in EPSG:3310 so they are areal, then returned in
    EPSG:4326. The input needs a geoid_bg column and polygon geometry.
    """
    # Reset the index first. A non-contiguous input index would misalign the
    # centroid GeoSeries against the plain column arrays and silently produce
    # NaN geometries for unmatched rows.
    polys = block_group_polygons.reset_index(drop=True).to_crs("EPSG:3310")
    geoids = polys["geoid_bg"].astype(str).to_numpy()
    centroids = polys.geometry.centroid
    out = gpd.GeoDataFrame(
        {ORIGIN: geoids, "geoid_bg": geoids},
        geometry=centroids.to_numpy(),
        crs="EPSG:3310",
    ).to_crs("EPSG:4326")

    # Conservation guard against the exact bug this replaced. Every non-empty
    # input polygon must yield a finite centroid. A drop to NaN, from an index
    # misalignment, must raise rather than pass silently.
    n_valid_in = int(
        (block_group_polygons.geometry.notna() & ~block_group_polygons.geometry.is_empty).sum()
    )
    finite_out = out.geometry.notna().to_numpy() & np.isfinite(out.geometry.x.to_numpy()) & np.isfinite(
        out.geometry.y.to_numpy()
    )
    if int(finite_out.sum()) != n_valid_in:
        raise ValueError(
            f"geometric_centroids produced {int(finite_out.sum())} finite centroids "
            f"for {n_valid_in} non-empty input polygons. Rows were lost to NaN."
        )
    return out


def download_centers_file(cfg: Config, state: str = "06", dest: Path | None = None) -> Path:
    """Download the state block group centers of population file."""
    url = cfg["access"]["centers_of_population"]["blkgrp_url_template"].format(state=state)
    dest = dest or (cfg.path("raw") / f"CenPop2020_Mean_BG{state}.txt")
    dest.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=REQUEST_TIMEOUT_S)
    response.raise_for_status()
    # Write raw bytes. Writing response.text would let a wrong guessed encoding
    # mojibake the byte order mark, which corrupts the header on reload.
    dest.write_bytes(response.content)
    return dest


def population_weighted_centroids(
    cfg: Config | None = None, state: str = "06", path: Path | None = None
) -> gpd.GeoDataFrame:
    """Load population weighted centroids for the in-scope counties."""
    cfg = cfg or load_config()
    counties = {fips(c) for c in cfg.all_county_fips}
    path = path or (cfg.path("raw") / f"CenPop2020_Mean_BG{state}.txt")
    if not path.exists():
        path = download_centers_file(cfg, state, path)
    # utf-8-sig drops the byte order mark the Census file carries on its header.
    df = parse_centers_of_population(path.read_text(encoding="utf-8-sig"))
    return centers_to_geodataframe(df, counties)


def load_centroids(cfg: Config, mode: str | None = None, **kwargs) -> gpd.GeoDataFrame:
    """Dispatch to the configured centroid mode."""
    mode = mode or cfg["access"]["centroid_mode"]
    if mode == "population_weighted":
        return population_weighted_centroids(cfg, **kwargs)
    if mode == "geometric":
        polys = kwargs.get("block_group_polygons")
        if polys is None:
            raise ValueError(
                "geometric centroid mode needs block_group_polygons, the TIGER "
                "block group geometry for the in-scope counties"
            )
        return geometric_centroids(polys)
    raise ValueError(f"unknown centroid_mode {mode}")


def run(cfg: Config | None = None) -> gpd.GeoDataFrame:
    """Build and write population weighted centroids for the in-scope counties.

    Writes data/processed/blockgroup_centroids.parquet. Redistributable.
    """
    from src.utils import ensure_dir, utc_now_iso, write_manifest

    cfg = cfg or load_config()
    gdf = population_weighted_centroids(cfg)
    processed = ensure_dir(cfg.path("processed"))
    gdf.to_parquet(processed / "blockgroup_centroids.parquet")
    write_manifest(
        cfg.path("manifests") / "blockgroup_centroids.manifest.json",
        {
            "source": "2020 Census block group centers of population",
            "centroid_mode": "population_weighted",
            "block_group_count": int(len(gdf)),
            "total_population": int(gdf["population"].sum()),
            "built_at_utc": utc_now_iso(),
            "license": "Public domain, U.S. Census Bureau.",
            "redistributable": True,
        },
    )
    print(f"Centroids: {len(gdf)} block groups, population weighted")
    return gdf


if __name__ == "__main__":
    run()
