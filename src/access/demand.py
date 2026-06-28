"""Demand layers for the accessibility math.

Residential population is the L2 demand and the primary DCFC demand. It comes
from the Phase 1 ACS pull.

LODES workplace jobs is the pre-specified DCFC demand sensitivity. It comes from
the LEHD LODES8 Workplace Area Characteristics for California, at block level,
with no API key. Jobs are summed to the block group. The reasoning is that fast
charging often serves trips anchored at work and other non home destinations, so
a workplace weighted demand is a sensible alternate denominator for DCFC.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

from src.config import Config, fips, load_config

REQUEST_TIMEOUT_S = 300
RESIDENTIAL_FIELD = "B01003_001E"


def residential_from_acs(acs_df: pd.DataFrame) -> pd.Series:
    """Total population per block group as a demand series, indexed by geoid_bg."""
    df = acs_df.copy()
    df["geoid_bg"] = df["geoid_bg"].astype(str)
    pop = pd.to_numeric(df[RESIDENTIAL_FIELD], errors="coerce").fillna(0.0)
    return pd.Series(pop.to_numpy(), index=df["geoid_bg"], name="residential")


def wac_jobs_to_blockgroup(wac_df: pd.DataFrame, jobs_field: str = "C000") -> pd.Series:
    """Sum LODES WAC block level jobs to the block group, indexed by geoid_bg.

    w_geocode is the 15 digit 2020 block GEOID. The block group is its first 12
    digits. Jobs are the C000 total.
    """
    df = wac_df.copy()
    df["w_geocode"] = df["w_geocode"].astype(str).str.zfill(15)
    df["geoid_bg"] = df["w_geocode"].str[:12]
    jobs = pd.to_numeric(df[jobs_field], errors="coerce").fillna(0.0)
    grouped = jobs.groupby(df["geoid_bg"]).sum()
    grouped.name = "lodes_wac"
    return grouped


def residential_demand(cfg: Config | None = None) -> pd.Series:
    """Load residential demand from the processed ACS block group table."""
    cfg = cfg or load_config()
    acs = pd.read_parquet(cfg.path("processed") / "acs_blockgroups.parquet")
    return residential_from_acs(acs)


def download_wac(cfg: Config, dest: Path | None = None) -> Path:
    """Download the California LODES WAC gzip, no API key required."""
    lodes = cfg["lodes"]
    url = lodes["wac_url_template"].format(
        state_abbr=lodes["state_abbr"], year=lodes["year"]
    )
    dest = dest or (cfg.path("raw") / f"{lodes['state_abbr']}_wac_S000_JT00_{lodes['year']}.csv.gz")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=REQUEST_TIMEOUT_S) as response:
        response.raise_for_status()
        with open(dest, "wb") as handle:
            for chunk in response.iter_content(chunk_size=1 << 20):
                handle.write(chunk)
    return dest


def lodes_wac_demand(cfg: Config | None = None, path: Path | None = None) -> pd.Series:
    """Load LODES WAC demand for the in-scope counties, summed to block group."""
    cfg = cfg or load_config()
    counties = {fips(c) for c in cfg.all_county_fips}
    lodes = cfg["lodes"]
    path = path or (cfg.path("raw") / f"{lodes['state_abbr']}_wac_S000_JT00_{lodes['year']}.csv.gz")
    if not path.exists():
        path = download_wac(cfg, path)
    wac = pd.read_csv(path, dtype={"w_geocode": str})
    series = wac_jobs_to_blockgroup(wac, lodes["jobs_field"])
    return series[series.index.str[:5].isin(counties)]


def load_demand(cfg: Config, spec: str) -> pd.Series:
    """Dispatch to a named demand layer."""
    if spec == "residential":
        return residential_demand(cfg)
    if spec == "lodes_wac":
        return lodes_wac_demand(cfg)
    raise ValueError(f"unknown demand spec {spec}")


def run(cfg: Config | None = None) -> pd.Series:
    """Build and write the LODES WAC demand layer for the in-scope counties.

    Writes data/processed/demand_lodes_wac.parquet. Redistributable.
    """
    from src.utils import ensure_dir, utc_now_iso, write_manifest

    cfg = cfg or load_config()
    jobs = lodes_wac_demand(cfg)
    processed = ensure_dir(cfg.path("processed"))
    jobs.rename("jobs").to_frame().reset_index().to_parquet(
        processed / "demand_lodes_wac.parquet", index=False
    )
    write_manifest(
        cfg.path("manifests") / "demand_lodes_wac.manifest.json",
        {
            "source": "LEHD LODES8 Workplace Area Characteristics, California",
            "year": cfg["lodes"]["year"],
            "jobs_field": cfg["lodes"]["jobs_field"],
            "block_group_count": int(len(jobs)),
            "total_jobs": int(jobs.sum()),
            "built_at_utc": utc_now_iso(),
            "license": "Public domain, U.S. Census Bureau LEHD. Attribution requested.",
            "redistributable": True,
        },
    )
    print(f"LODES WAC demand: {len(jobs)} block groups, {int(jobs.sum())} jobs")
    return jobs


if __name__ == "__main__":
    run()
