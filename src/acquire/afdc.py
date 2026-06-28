"""AFDC station acquisition.

Pulls EV charging stations from the NREL Alternative Fuel Data Center API,
filtered to California and the ELEC fuel type. Stations and ports are kept as
distinct objects. A dated snapshot is written to data/snapshots with a sha256
and a manifest of the exact query parameters and pull date, so the pull can be
reproduced and later deposited to Zenodo.

AFDC changes daily. The snapshot is the frozen record of record.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from src.config import Config, load_config
from src.utils import (
    ensure_dir,
    sha256_bytes,
    sha256_file,
    utc_date,
    utc_now_iso,
    write_manifest,
)

REQUEST_TIMEOUT_S = 120


def build_query_params(cfg: Config, api_key: str) -> dict[str, str]:
    """Build the exact AFDC query parameters. Recorded verbatim in the manifest."""
    afdc = cfg["afdc"]
    return {
        "api_key": api_key,
        "fuel_type": afdc["fuel_type"],
        "state": afdc["state"],
        "status": afdc["status"],
        "access": afdc["access"],
        "limit": "all",
    }


def _redact(params: dict[str, str]) -> dict[str, str]:
    """Copy of params with the API key removed, safe to store in a manifest."""
    return {k: v for k, v in params.items() if k != "api_key"}


def fetch_raw(cfg: Config, api_key: str) -> bytes:
    """Fetch the raw AFDC JSON payload as bytes. Bytes are hashed for the snapshot."""
    params = build_query_params(cfg, api_key)
    response = requests.get(
        cfg["afdc"]["base_url"], params=params, timeout=REQUEST_TIMEOUT_S
    )
    response.raise_for_status()
    return response.content


def parse_stations(raw: dict[str, Any]) -> pd.DataFrame:
    """Parse the station objects. One row per station.

    Coordinates, network, and access are captured. Connector counts stay here
    too as a convenience, but the per port split lives in parse_ports.
    """
    stations = raw.get("fuel_stations", [])
    rows = []
    for s in stations:
        rows.append(
            {
                "station_id": str(s.get("id")),
                "station_name": s.get("station_name"),
                "latitude": s.get("latitude"),
                "longitude": s.get("longitude"),
                "ev_network": s.get("ev_network"),
                "access_code": s.get("access_code"),
                "access_days_time": s.get("access_days_time"),
                "status_code": s.get("status_code"),
                "street_address": s.get("street_address"),
                "city": s.get("city"),
                "state": s.get("state"),
                "zip": s.get("zip"),
                "ev_pricing": s.get("ev_pricing"),
                "owner_type_code": s.get("owner_type_code"),
                "facility_type": s.get("facility_type"),
                "ev_dc_fast_num": s.get("ev_dc_fast_num"),
                "ev_level2_evse_num": s.get("ev_level2_evse_num"),
                "ev_connector_types": ";".join(s.get("ev_connector_types") or []),
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df["station_id"] = df["station_id"].astype(str)
    return df


def parse_ports(raw: dict[str, Any]) -> pd.DataFrame:
    """Parse ports. Per connector counts split into DCFC and L2 rows.

    Each station yields up to two rows, one for DCFC ports and one for L2 ports,
    each carrying the port count and the connector types. Zero or missing counts
    are dropped so the table holds only real ports.
    """
    stations = raw.get("fuel_stations", [])
    rows = []
    for s in stations:
        station_id = str(s.get("id"))
        connectors = ";".join(s.get("ev_connector_types") or [])
        dcfc = s.get("ev_dc_fast_num")
        l2 = s.get("ev_level2_evse_num")
        if dcfc:
            rows.append(
                {
                    "station_id": station_id,
                    "port_class": "DCFC",
                    "port_count": int(dcfc),
                    "connector_types": connectors,
                }
            )
        if l2:
            rows.append(
                {
                    "station_id": station_id,
                    "port_class": "L2",
                    "port_count": int(l2),
                    "connector_types": connectors,
                }
            )
    df = pd.DataFrame(rows, columns=["station_id", "port_class", "port_count", "connector_types"])
    if not df.empty:
        df["station_id"] = df["station_id"].astype(str)
    return df


# The AFDC bulk CSV from afdc.energy.gov uses human readable column names, which
# differ from the developer API JSON keys the parser above was written against.
# This map adapts the bulk schema to the same record shape, so parse_stations and
# parse_ports work unchanged. Schema differences noted:
#   "EV DC Fast Count"   -> ev_dc_fast_num    (Count, not Num)
#   "EV Level2 EVSE Num" -> ev_level2_evse_num
#   "EV Connector Types" is a space separated string, not a JSON list
#   the bulk CSV has no County column, so county is assigned by point in polygon
BULK_TO_API = {
    "ID": "id",
    "Station Name": "station_name",
    "Latitude": "latitude",
    "Longitude": "longitude",
    "EV Network": "ev_network",
    "Status Code": "status_code",
    "Access Code": "access_code",
    "EV DC Fast Count": "ev_dc_fast_num",
    "EV Level2 EVSE Num": "ev_level2_evse_num",
    "State": "state",
    "City": "city",
    "ZIP": "zip",
}


def read_bulk_csv(path: Path | str) -> dict[str, Any]:
    """Read the AFDC bulk ELEC CSV into the same dict shape as the API JSON.

    Returns a {"fuel_stations": [...]} dict so parse_stations and parse_ports
    consume it without change. Connector types are split from the space separated
    bulk string into a list. Only ELEC rows are kept.
    """
    df = pd.read_csv(path, low_memory=False)
    if "Fuel Type Code" in df.columns:
        df = df[df["Fuel Type Code"] == "ELEC"]

    stations: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        conn = r.get("EV Connector Types")
        conn_list = str(conn).split() if pd.notna(conn) else []
        station = {api: r.get(bulk) for bulk, api in BULK_TO_API.items()}
        for num_field in ("ev_dc_fast_num", "ev_level2_evse_num"):
            value = station.get(num_field)
            station[num_field] = None if value is None or pd.isna(value) else value
        station["ev_connector_types"] = conn_list
        stations.append(station)
    return {"fuel_stations": stations, "total_results": len(stations)}


def write_snapshot(
    raw_bytes: bytes,
    cfg: Config,
    params: dict[str, str],
    pull_date: str | None = None,
) -> dict[str, Any]:
    """Write a dated snapshot, its sha256, and a reproducibility manifest.

    Returns the manifest dict. The snapshot file holds the raw API bytes exactly
    as received, so its sha256 is stable and verifiable.
    """
    pull_date = pull_date or utc_date()
    snap_dir = ensure_dir(cfg.path("snapshots"))
    snapshot_path = snap_dir / f"afdc_ca_elec_{pull_date}.json"
    snapshot_path.write_bytes(raw_bytes)

    digest = sha256_file(snapshot_path)
    manifest = {
        "source": "AFDC NREL Alternative Fuel Data Center",
        "endpoint": cfg["afdc"]["base_url"],
        "query_params": _redact(params),
        "pull_date": pull_date,
        "pulled_at_utc": utc_now_iso(),
        "snapshot_file": snapshot_path.name,
        "sha256": digest,
        "byte_count": len(raw_bytes),
        "license": "Public domain, U.S. Department of Energy. Attribution requested.",
        "redistributable": True,
        "note": "Frozen for reproducibility. AFDC changes daily.",
    }
    manifest_path = cfg.path("manifests") / f"afdc_ca_elec_{pull_date}.manifest.json"
    write_manifest(manifest_path, manifest)
    return manifest


def verify_snapshot(snapshot_path: Path, expected_sha256: str) -> bool:
    """Recompute the snapshot sha256 and compare to the recorded value."""
    return sha256_file(snapshot_path) == expected_sha256


def run(cfg: Config | None = None) -> dict[str, Any]:
    """Live pull, snapshot, parse, and write processed tables.

    Requires the NREL API key on the environment. Writes:
      data/snapshots/afdc_ca_elec_<date>.json   raw frozen snapshot
      manifests/afdc_ca_elec_<date>.manifest.json
      data/processed/afdc_stations.parquet
      data/processed/afdc_ports.parquet
    """
    cfg = cfg or load_config()
    api_key = cfg.require_secret(cfg["afdc"]["api_key_env"])
    params = build_query_params(cfg, api_key)

    raw_bytes = fetch_raw(cfg, api_key)
    manifest = write_snapshot(raw_bytes, cfg, params)

    raw = json.loads(raw_bytes)
    stations = parse_stations(raw)
    ports = parse_ports(raw)

    processed = ensure_dir(cfg.path("processed"))
    stations.to_parquet(processed / "afdc_stations.parquet", index=False)
    ports.to_parquet(processed / "afdc_ports.parquet", index=False)

    print(
        f"AFDC stations: {len(stations)} ports rows: {len(ports)} "
        f"sha256: {manifest['sha256'][:12]}..."
    )
    return manifest


if __name__ == "__main__":
    run()
