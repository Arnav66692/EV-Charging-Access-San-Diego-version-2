"""ACS block group acquisition.

Pulls American Community Survey 5 year data at the block group level for the
three in-scope counties. Captures total population, tenure, and units in
structure. FIPS identifiers are strings with leading zeros preserved. The
vintage is recorded so the release is unambiguous.

Vintage 2023 is the 2019 to 2023 five year release.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import requests

from src.config import Config, fips, load_config
from src.utils import ensure_dir, utc_now_iso, write_manifest

REQUEST_TIMEOUT_S = 120


def variable_list(cfg: Config) -> list[str]:
    """Flatten the configured ACS variables into a single ordered list."""
    groups = cfg["acs"]["variables"]
    out: list[str] = []
    for key in ("total_population", "tenure", "units_in_structure"):
        out.extend(groups[key])
    return out


def build_url(cfg: Config) -> str:
    acs = cfg["acs"]
    return f"{acs['base_url']}/{acs['vintage']}/{acs['dataset']}"


def fetch_county(
    cfg: Config, state_fips: str, county_fips: str, api_key: str | None
) -> list[list[str]]:
    """Fetch block group rows for one county. Returns the raw Census matrix.

    The Census API returns a list of lists. The first row is the header.
    Block group geography needs state and county. The tract wildcard is implied.
    """
    variables = variable_list(cfg)
    params = {
        "get": ",".join(["NAME", *variables]),
        "for": "block group:*",
        "in": f"state:{state_fips} county:{county_fips}",
    }
    if api_key:
        params["key"] = api_key
    response = requests.get(build_url(cfg), params=params, timeout=REQUEST_TIMEOUT_S)
    response.raise_for_status()

    # The Census API answers a missing or invalid key with an HTML page and a
    # 200 status, not a JSON error. Detect that and fail with a clear message.
    if "missing_key" in response.url or "text/html" in response.headers.get(
        "content-type", ""
    ):
        raise RuntimeError(
            "Census API rejected the request. A valid CENSUS_API_KEY is required. "
            "Add it to .env or export it. Request a key at "
            "https://api.census.gov/data/key_signup.html"
        )
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Census API returned a non JSON body for county "
            f"{state_fips}{county_fips}: {response.text[:200]}"
        ) from exc


def parse_matrix(matrix: list[list[str]]) -> pd.DataFrame:
    """Convert a Census response matrix to a DataFrame with string FIPS GEOIDs."""
    header, *rows = matrix
    df = pd.DataFrame(rows, columns=header)

    # Geographic component columns come back as the trailing fields.
    geo_cols = ["state", "county", "tract", "block group"]
    for col in geo_cols:
        df[col] = df[col].astype(str)

    # Build canonical GEOIDs as strings. Block group GEOID is 12 chars,
    # tract GEOID is 11 chars. Leading zeros preserved throughout.
    df["geoid_bg"] = (
        df["state"].str.zfill(2)
        + df["county"].str.zfill(3)
        + df["tract"].str.zfill(6)
        + df["block group"].str.zfill(1)
    )
    df["geoid_tract"] = (
        df["state"].str.zfill(2)
        + df["county"].str.zfill(3)
        + df["tract"].str.zfill(6)
    )
    df["county_fips"] = df["state"].str.zfill(2) + df["county"].str.zfill(3)

    # Numeric measure columns. Census sends them as strings, negatives are
    # annotation flags for missing data and are coerced to NaN.
    measure_cols = [c for c in df.columns if c.startswith("B")]
    for col in measure_cols:
        numeric = pd.to_numeric(df[col], errors="coerce")
        df[col] = numeric.where(numeric >= 0)

    return df


def run(cfg: Config | None = None) -> pd.DataFrame:
    """Pull all in-scope counties, write a per-territory aware processed table.

    Writes data/processed/acs_blockgroups.parquet and a vintage manifest.
    """
    cfg = cfg or load_config()
    api_key = cfg.secret(cfg["acs"]["api_key_env"])  # optional but recommended

    frames = []
    for county_fips in cfg.all_county_fips:
        county_fips = fips(county_fips)
        state_fips, county_only = county_fips[:2], county_fips[2:]
        matrix = fetch_county(cfg, state_fips, county_only, api_key)
        frames.append(parse_matrix(matrix))

    combined = pd.concat(frames, ignore_index=True)
    combined.attrs["acs_vintage"] = cfg["acs"]["vintage"]

    processed = ensure_dir(cfg.path("processed"))
    combined.to_parquet(processed / "acs_blockgroups.parquet", index=False)

    manifest = {
        "source": "Census American Community Survey 5 year",
        "endpoint": build_url(cfg),
        "vintage": cfg["acs"]["vintage"],
        "span": cfg["acs"]["span"],
        "span_years": cfg["acs"]["span_years"],
        "geography": "block group",
        "counties": cfg.all_county_fips,
        "variables": variable_list(cfg),
        "row_count": int(len(combined)),
        "pulled_at_utc": utc_now_iso(),
        "license": "Public domain, U.S. Census Bureau.",
        "redistributable": True,
    }
    write_manifest(cfg.path("manifests") / "acs_blockgroups.manifest.json", manifest)
    print(f"ACS block groups: {len(combined)} rows, vintage {cfg['acs']['vintage']}")
    return combined


if __name__ == "__main__":
    run()
