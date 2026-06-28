"""The AFDC snapshot matches its recorded sha256."""

from __future__ import annotations

import json

from src.acquire.afdc import (
    parse_ports,
    parse_stations,
    read_bulk_csv,
    verify_snapshot,
    write_snapshot,
)
from src.config import load_config
from src.utils import (
    read_gzip_snapshot,
    read_manifest,
    sha256_bytes,
    sha256_file,
    write_gzip_snapshot,
)

cfg = load_config()


def test_read_bulk_csv_maps_schema_to_parser(tmp_path):
    # The AFDC bulk CSV uses human readable headers that differ from the API JSON.
    # read_bulk_csv must map them so parse_stations and parse_ports work unchanged.
    csv = (
        "Fuel Type Code,ID,Station Name,Latitude,Longitude,EV Network,Status Code,"
        "Access Code,EV DC Fast Count,EV Level2 EVSE Num,EV Connector Types,State,City,ZIP\n"
        "ELEC,1001,Both,32.7,-117.1,ChargePoint,E,public,4,8,CHADEMO J1772COMBO,CA,San Diego,92101\n"
        "ELEC,1002,L2only,33.6,-117.8,EVConnect,E,public,,6,J1772,CA,Irvine,92606\n"
        "LNG,9999,NotElec,34.0,-118.2,X,E,public,5,5,NA,CA,LA,90012\n"
    )
    path = tmp_path / "bulk.csv"
    path.write_text(csv)

    raw = read_bulk_csv(path)
    # The non ELEC row is dropped.
    assert len(raw["fuel_stations"]) == 2
    stations = parse_stations(raw)
    ports = parse_ports(raw)
    assert set(stations["station_id"]) == {"1001", "1002"}

    dcfc = ports[ports["port_class"] == "DCFC"]
    l2 = ports[ports["port_class"] == "L2"]
    # Station 1001 has both, 1002 has L2 only. "EV DC Fast Count" maps to DCFC.
    assert set(dcfc["station_id"]) == {"1001"}
    assert dcfc[dcfc["station_id"] == "1001"]["port_count"].iloc[0] == 4
    assert set(l2["station_id"]) == {"1001", "1002"}
    # Connector types split from the space separated bulk string.
    assert "CHADEMO" in stations[stations["station_id"] == "1001"]["ev_connector_types"].iloc[0]


def test_gzip_snapshot_roundtrip_and_stable_sha256(tmp_path):
    # The SCE and SDG&E freeze write gzip snapshots and record the sha256 of the
    # uncompressed content. The content must round trip, and the digest must be
    # stable across two writes of the same bytes.
    payload = b'{"type":"FeatureCollection","features":[1,2,3]}'
    p1 = write_gzip_snapshot(tmp_path / "a.geojson.gz", payload)
    p2 = write_gzip_snapshot(tmp_path / "b.geojson.gz", payload)
    assert read_gzip_snapshot(p1) == payload
    assert sha256_bytes(read_gzip_snapshot(p1)) == sha256_bytes(payload)
    # Pinned gzip header means identical content yields identical containers.
    assert p1.read_bytes() == p2.read_bytes()


def test_committed_snapshot_matches_recorded_sha256():
    snapshot = cfg.path("snapshots") / "afdc_ca_elec_sample.json"
    manifest = read_manifest(
        cfg.path("manifests") / "afdc_ca_elec_sample.manifest.json"
    )
    assert snapshot.exists()
    assert verify_snapshot(snapshot, manifest["sha256"])
    assert sha256_file(snapshot) == manifest["sha256"]


def test_write_snapshot_roundtrip(tmp_path, monkeypatch, sample_afdc_raw):
    # Redirect snapshot and manifest output into a temp dir.
    monkeypatch.setitem(cfg.data["paths"], "snapshots", str(tmp_path / "snap"))
    monkeypatch.setitem(cfg.data["paths"], "manifests", str(tmp_path / "man"))

    raw_bytes = json.dumps(sample_afdc_raw).encode("utf-8")
    params = {"api_key": "SECRET", "fuel_type": "ELEC", "state": "CA"}
    manifest = write_snapshot(raw_bytes, cfg, params, pull_date="2026-01-01")

    snapshot_path = cfg.path("snapshots") / manifest["snapshot_file"]
    assert snapshot_path.exists()
    assert verify_snapshot(snapshot_path, manifest["sha256"])
    # The API key is never written into the manifest.
    assert "api_key" not in manifest["query_params"]


def test_tampered_snapshot_fails_verification(tmp_path, monkeypatch, sample_afdc_raw):
    monkeypatch.setitem(cfg.data["paths"], "snapshots", str(tmp_path / "snap"))
    monkeypatch.setitem(cfg.data["paths"], "manifests", str(tmp_path / "man"))

    raw_bytes = json.dumps(sample_afdc_raw).encode("utf-8")
    manifest = write_snapshot(raw_bytes, cfg, {"api_key": "x"}, pull_date="2026-01-01")
    snapshot_path = cfg.path("snapshots") / manifest["snapshot_file"]

    snapshot_path.write_bytes(raw_bytes + b" tampered")
    assert not verify_snapshot(snapshot_path, manifest["sha256"])


def test_stations_and_ports_are_distinct_objects(sample_afdc_raw):
    stations = parse_stations(sample_afdc_raw)
    ports = parse_ports(sample_afdc_raw)
    # Three stations in, three station rows out.
    assert len(stations) == 3
    # Ports split DCFC and L2. Site one has both, site two L2 only, site three DCFC only.
    assert len(ports) == 4
    dcfc = ports[ports["port_class"] == "DCFC"]
    l2 = ports[ports["port_class"] == "L2"]
    assert set(dcfc["station_id"]) == {"1001", "1003"}
    assert set(l2["station_id"]) == {"1001", "1002"}
    assert dcfc[dcfc["station_id"] == "1001"]["port_count"].iloc[0] == 4
    # Station ids are strings.
    assert stations["station_id"].map(lambda v: isinstance(v, str)).all()
