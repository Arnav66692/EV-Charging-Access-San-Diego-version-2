"""Build the public web map's static data from DERIVED outputs only.

FIREWALL (legal boundary): no SDG&E load-capacity value, raw or rounded, may
reach the browser. This builder ships only modeled access, per-county relative
access, percentile, the DAC flag, and derived candidate feasibility tiers, never
a utility load column. It asserts the forbidden field names are absent before
writing, and tests/test_web_firewall.py re-checks the output as the release gate.

Run:  python scripts/build_web_data.py
Out:  web/data/{block_groups,counties,candidates}.geojson
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root, for `python scripts/...`

from src.access.dac_ratio import weighted_median
from src.config import load_config

COUNTY = {"06073": "San Diego", "06059": "Orange", "06037": "LA"}
ALBERS = "EPSG:3310"
LOW_POP = 200  # block groups below this population get the rural-overstatement flag
COORD_DECIMALS = 5  # ~1.1 m, plenty for a web choropleth
FORBIDDEN = re.compile(
    r"ICAWNOF_UNILOAD|ICAWOF_UNILOAD|UNILOAD|ica_overall_load|"
    r"load_capacity_mw|section_mw|hosting_capacity",
    re.IGNORECASE,
)


def _round_coords(x):
    if isinstance(x, float):
        return round(x, COORD_DECIMALS)
    if isinstance(x, list):
        return [_round_coords(v) for v in x]
    return x


def _write_geojson(gdf: gpd.GeoDataFrame, path: Path, name: str) -> None:
    """Serialize minified, drop the redundant CRS member, and assert the firewall."""
    gj = json.loads(gdf.to_json(drop_id=True))
    gj["name"] = name
    gj.pop("crs", None)  # CRS84 is the GeoJSON default
    for feat in gj["features"]:
        feat["geometry"]["coordinates"] = _round_coords(feat["geometry"]["coordinates"])
    text = json.dumps(gj, separators=(",", ":"))
    leak = sorted({m.group(0) for m in FORBIDDEN.finditer(text)})
    if leak:
        raise SystemExit(f"FIREWALL: refusing to write {name}, forbidden token(s) {leak}")
    path.write_text(text, encoding="utf-8")
    print(f"  {path.name}: {len(gj['features'])} features, {len(text) / 1e6:.1f} MB (firewall clean)")


def _max_tier(row: pd.Series) -> str:
    if bool(row["capacity_unknown"]):
        return "unknown"
    for tier in ("large", "medium", "small"):
        if row.get(f"feasible_{tier}") is True:
            return tier
    return "none"


def main() -> None:
    cfg = load_config()
    proc = cfg.path("processed")
    out = cfg.root / "web" / "data"
    out.mkdir(parents=True, exist_ok=True)
    bg_zip = f"zip://{cfg.path('raw') / 'tl_2024_06_bg.zip'}"

    # --- derived inputs (all my outputs, no utility load values) ---
    acs = pd.read_parquet(proc / "acs_blockgroups.parquet")
    acs["geoid_bg"] = acs["geoid_bg"].astype(str)
    pop = pd.Series(
        pd.to_numeric(acs["B01003_001E"], errors="coerce").fillna(0).to_numpy(),
        index=acs["geoid_bg"],
    )
    ces = pd.read_parquet(proc / "ces_dac_blockgroups.parquet")
    dac = pd.Series(ces["dac_flag"].to_numpy(), index=ces["geoid_bg"].astype(str), dtype="boolean")

    surf = pd.read_parquet(proc / "access_3county_euclidean.parquet")
    surf = surf[(surf.charger_type == "dcfc") & (surf.method == "g2sfca") & (surf.demand_spec == "residential")]
    acc = pd.Series(surf["access"].to_numpy(), index=surf["geoid_bg"].astype(str))
    acc_in = acc[acc.index.str[:5].isin(COUNTY)]

    # statewide-comparable percentile, and per-county relative access (the localized finding)
    pct = acc_in.rank(pct=True) * 100.0
    nondac_median: dict[str, float] = {}
    for code in COUNTY:
        ids = acc_in.index[acc_in.index.str[:5] == code]
        a = acc_in.reindex(ids).to_numpy()
        d = dac.reindex(ids).fillna(False).astype(bool).to_numpy()
        w = pop.reindex(ids).fillna(0).to_numpy()
        nondac_median[code] = weighted_median(a[~d], w[~d])

    # --- block group polygons (TIGER, public), simplified for web ---
    bg = gpd.read_file(bg_zip)
    bg = bg[(bg.STATEFP == "06") & (bg.COUNTYFP.isin(["073", "059", "037"]))][["GEOID", "geometry"]]
    bg = bg.rename(columns={"GEOID": "geoid_bg"}).to_crs(ALBERS)
    bg["geometry"] = bg.geometry.simplify(120).buffer(0)
    bg = bg.to_crs("EPSG:4326")
    bg["geoid_bg"] = bg["geoid_bg"].astype(str)
    bg["county"] = bg["geoid_bg"].str[:5].map(COUNTY)
    bg["access"] = bg["geoid_bg"].map(acc).round(7)
    bg["rel_access"] = bg.apply(
        lambda r: round(r["access"] / nondac_median[r["geoid_bg"][:5]], 3)
        if pd.notna(r["access"]) and nondac_median[r["geoid_bg"][:5]]
        else None,
        axis=1,
    )
    bg["pctile"] = bg["geoid_bg"].map(pct).round(1)
    bg["is_dac"] = bg["geoid_bg"].map(lambda g: bool(dac.get(g)) if pd.notna(dac.get(g)) else None)
    bg["pop"] = bg["geoid_bg"].map(pop).round(0)
    bg["low_pop"] = bg["pop"] < LOW_POP
    bg = bg.dropna(subset=["access"]).copy()
    cols = ["geoid_bg", "county", "access", "rel_access", "pctile", "is_dac", "pop", "low_pop", "geometry"]
    _write_geojson(bg[cols], out / "block_groups.geojson", "block_groups")

    # --- county boundaries ---
    cb = gpd.read_file(bg_zip)
    cb = cb[(cb.STATEFP == "06") & (cb.COUNTYFP.isin(["073", "059", "037"]))].copy()
    cb["county"] = "06" + cb["COUNTYFP"]
    cb = cb.dissolve("county").reset_index()[["county", "geometry"]]
    cb["name"] = cb["county"].map(COUNTY)
    cb = cb.to_crs(ALBERS)
    cb["geometry"] = cb.geometry.simplify(200)
    cb = cb.to_crs("EPSG:4326")
    _write_geojson(cb[["county", "name", "geometry"]], out / "counties.geojson", "counties")

    # --- candidate feasibility, DERIVED tiers only, NO load MW ---
    cand = gpd.read_parquet(proc / "candidate_sites.parquet")[["candidate_id", "county_fips", "geometry"]]
    cand["candidate_id"] = cand["candidate_id"].astype(str)
    feas = pd.concat(
        [pd.read_parquet(proc / "grid_feasibility_sdge.parquet"), pd.read_parquet(proc / "grid_feasibility_sce.parquet")],
        ignore_index=True,
    )
    feas["candidate_id"] = feas["candidate_id"].astype(str)
    feas["tier"] = feas.apply(_max_tier, axis=1)
    cf = cand.merge(feas[["candidate_id", "tier"]], on="candidate_id", how="inner")
    cf["county"] = cf["county_fips"].map(COUNTY)
    cf = cf[cf["tier"].isin(["small", "medium", "large"])].copy()  # ship only feasible-classified points
    _write_geojson(cf[["candidate_id", "county", "tier", "geometry"]], out / "candidates.geojson", "candidates")

    print("county non-DAC medians:", {COUNTY[k]: round(v, 7) for k, v in nondac_median.items()})


if __name__ == "__main__":
    main()
