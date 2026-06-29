"""OSM candidate sites and the OSRM routing extract.

Two responsibilities live here.

First, build a candidate site list from public facilities in OpenStreetMap for
the three in-scope counties. Candidate types are parking lots, civic sites,
retail anchors, and park and rides. These are points where a fast charger could
plausibly be sited. OSM is redistributable under the ODbL with attribution.

Second, a helper to download the California OSM extract from Geofabrik, the
input that the OSRM car profile instance is built from. See README for storage
and RAM needs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point

from src.config import Config, fips, load_config
from src.utils import ensure_dir, utc_now_iso, write_manifest

REQUEST_TIMEOUT_S = 300

# County FIPS to the administrative name OSM uses for the boundary area.
COUNTY_OSM_NAME = {
    "06073": "San Diego County",
    "06059": "Orange County",
    "06037": "Los Angeles County",
}


def build_overpass_query(county_name: str, timeout_s: int) -> str:
    """Build an Overpass QL query for candidate facilities within a county.

    The county administrative boundary defines the search area. The county is
    scoped within California first, because county names like Orange County are
    not unique across the United States and an unscoped name match pulls in other
    states. Nodes and ways are returned with center coordinates so ways collapse
    to a single point.
    """
    return f"""
[out:json][timeout:{timeout_s}];
area["boundary"="administrative"]["admin_level"="4"]["name"="California"]->.ca;
rel(area.ca)["boundary"="administrative"]["admin_level"="6"]["name"="{county_name}"]->.r;
.r map_to_area->.a;
(
  node["amenity"="parking"](area.a);
  way["amenity"="parking"](area.a);
  node["amenity"~"^(townhall|library|community_centre)$"](area.a);
  way["amenity"~"^(townhall|library|community_centre)$"](area.a);
  node["shop"="supermarket"](area.a);
  way["shop"="supermarket"](area.a);
  node["park_ride"](area.a);
  way["park_ride"](area.a);
);
out center tags;
""".strip()


def _classify(tags: dict[str, Any]) -> str:
    """Map OSM tags to a coarse candidate facility type."""
    if tags.get("park_ride"):
        return "park_and_ride"
    if tags.get("amenity") == "parking":
        return "parking"
    if tags.get("amenity") in {"townhall", "library", "community_centre"}:
        return "civic"
    if tags.get("shop") == "supermarket":
        return "retail"
    return "other"


def fetch_overpass(query: str, cfg: Config) -> dict[str, Any]:
    response = requests.post(
        cfg["osm"]["overpass_url"],
        data={"data": query},
        headers={"User-Agent": "ev-grid-siting/1.0 (research, contact via repo)"},
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.json()


def elements_to_geodataframe(
    elements: list[dict[str, Any]], county_fips: str, cfg: Config
) -> gpd.GeoDataFrame:
    """Convert Overpass elements to a candidate point GeoDataFrame."""
    rows = []
    geoms = []
    for el in elements:
        if el["type"] == "node":
            lon, lat = el.get("lon"), el.get("lat")
        else:
            center = el.get("center") or {}
            lon, lat = center.get("lon"), center.get("lat")
        if lon is None or lat is None:
            continue
        tags = el.get("tags", {})
        rows.append(
            {
                "candidate_id": f"osm:{el['type']}/{el['id']}",
                "facility_type": _classify(tags),
                "name": tags.get("name"),
                "county_fips": fips(county_fips),
                "source": "osm",
            }
        )
        geoms.append(Point(lon, lat))
    gdf = gpd.GeoDataFrame(rows, geometry=geoms, crs=cfg.crs_storage)
    return gdf


def run(cfg: Config | None = None) -> gpd.GeoDataFrame:
    """Pull candidate sites for all in-scope counties.

    Writes data/processed/candidate_sites.parquet.
    """
    cfg = cfg or load_config()
    timeout_s = int(cfg["osm"]["timeout_s"])
    frames = []
    for county_fips in cfg.all_county_fips:
        county_fips = fips(county_fips)
        county_name = COUNTY_OSM_NAME[county_fips]
        query = build_overpass_query(county_name, timeout_s)
        data = fetch_overpass(query, cfg)
        frames.append(
            elements_to_geodataframe(data.get("elements", []), county_fips, cfg)
        )

    candidates = gpd.GeoDataFrame(
        pd.concat(frames, ignore_index=True), crs=cfg.crs_storage
    )
    # Drop exact duplicate candidate ids that can appear across overlapping queries.
    candidates = candidates.drop_duplicates(subset="candidate_id").reset_index(drop=True)

    processed = ensure_dir(cfg.path("processed"))
    candidates.to_parquet(processed / "candidate_sites.parquet")

    manifest = {
        "source": "OpenStreetMap via Overpass",
        "counties": cfg.all_county_fips,
        "candidate_count": int(len(candidates)),
        "facility_types": sorted(candidates["facility_type"].unique().tolist()),
        "pulled_at_utc": utc_now_iso(),
        "license": "OpenStreetMap contributors, ODbL. Attribution required.",
        "redistributable": True,
    }
    write_manifest(cfg.path("manifests") / "candidate_sites.manifest.json", manifest)
    print(f"OSM candidates: {len(candidates)} sites across {len(frames)} counties")
    return candidates


def download_geofabrik_extract(cfg: Config | None = None, dest: Path | None = None) -> Path:
    """Stream the California OSM extract to disk for the OSRM build.

    The file is large, roughly 1 GB. It lands under data/raw, which is
    gitignored. Building OSRM from it needs several GB of RAM. See README.
    """
    cfg = cfg or load_config()
    url = cfg["osrm"]["geofabrik_extract_url"]
    dest = dest or (cfg.path("raw") / "california-latest.osm.pbf")
    ensure_dir(dest.parent)
    with requests.get(url, stream=True, timeout=REQUEST_TIMEOUT_S) as response:
        response.raise_for_status()
        with open(dest, "wb") as handle:
            for chunk in response.iter_content(chunk_size=1 << 20):
                handle.write(chunk)
    print(f"Downloaded Geofabrik extract to {dest} ({dest.stat().st_size/1e6:.0f} MB)")
    return dest


if __name__ == "__main__":
    run()
