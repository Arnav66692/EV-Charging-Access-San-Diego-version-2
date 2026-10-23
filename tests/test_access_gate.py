"""The v1-compat gate runs end to end on fixtures and emits a result. Centroid
parsing works on the centers of population format."""

from __future__ import annotations

import json
import hashlib
import pytest
import geopandas as gpd
from shapely.geometry import Polygon

from src.access.centroids import (
    centers_to_geodataframe,
    geometric_centroids,
    parse_centers_of_population,
)
from src.access.gate import GateResult, run_gate, write_gate_result


def test_v1_compat_gate_runs_and_emits_result(gate_fixture, tmp_path):
    result = run_gate(
        origins=gate_fixture["origins"],
        supplies_dcfc=gate_fixture["supplies_dcfc"],
        residential=gate_fixture["residential"],
        dac_flags=gate_fixture["dac_flags"],
        population=gate_fixture["population"],
        radius_m=gate_fixture["radius_m"],
    )
    assert isinstance(result, GateResult)
    # No v1 snapshot provided, so the qualitative path runs.
    assert result.path_taken == "qualitative_pattern"
    # DCFC ratio below 1, DAC areas have lower SFCA access.
    assert result.sfca_dac_ratio < 1.0
    # Proximity reversal. Nearest distance flatters DAC more than SFCA does.
    assert result.naive_proximity_ratio > result.sfca_dac_ratio
    assert result.passed is True

    out = write_gate_result(tmp_path / "gate.json", result)
    assert out.exists()


def test_missing_snapshot_cannot_pass(gate_fixture, tmp_path):
    with pytest.raises(FileNotFoundError):
        run_gate(**gate_fixture, v1_snapshot_path=tmp_path / "absent.json",
                 v1_reference_ratio=0.7)


def test_comparison_reads_frozen_supply(gate_fixture, tmp_path):
    stations = []
    for _, row in gate_fixture["supplies_dcfc"].to_crs(4326).iterrows():
        stations.append(dict(id=row["supply_id"], latitude=row.geometry.y,
                             longitude=row.geometry.x, ev_dc_fast_num=row["capacity"],
                             status_code="E", access_code="public"))
    snapshot = tmp_path / "afdc.json"
    snapshot.write_text(json.dumps({"fuel_stations": stations}))
    reference = run_gate(**gate_fixture).sfca_dac_ratio
    # Prove supplied mutable stations are not used in the frozen comparison.
    changed = dict(gate_fixture)
    changed["supplies_dcfc"] = gate_fixture["supplies_dcfc"].iloc[:0]
    result = run_gate(**changed, v1_snapshot_path=snapshot,
                      v1_reference_ratio=reference, tolerance=0.00001)
    assert result.passed
    assert result.path_taken == "frozen_supply_comparison"
    assert result.details["snapshot_sha256"] == hashlib.sha256(snapshot.read_bytes()).hexdigest()
    assert "origins_sha256" in result.details
    assert not run_gate(**changed, v1_snapshot_path=snapshot,
                        v1_reference_ratio=reference + 1, tolerance=0.01).passed


def test_reference_requires_snapshot(gate_fixture):
    with pytest.raises(ValueError, match="both"):
        run_gate(**gate_fixture, v1_reference_ratio=0.7)


def test_centers_of_population_parse_and_geoid():
    text = (
        "STATEFP,COUNTYFP,TRACTCE,BLKGRPCE,POPULATION,LATITUDE,LONGITUDE\n"
        "06,073,008339,1,1500,+32.715700,-117.161100\n"
        "06,073,008339,2,1200,+32.720000,-117.150000\n"
        "06,037,101110,1,2050,+34.050000,-118.250000\n"
    )
    df = parse_centers_of_population(text)
    assert list(df["geoid_bg"]) == ["060730083391", "060730083392", "060371011101"]
    assert df["geoid_bg"].map(lambda v: isinstance(v, str)).all()
    assert df.loc[0, "population"] == 1500

    gdf = centers_to_geodataframe(df, counties={"06073"})
    # Only the two San Diego block groups survive the county filter.
    assert len(gdf) == 2
    assert gdf.crs.to_epsg() == 4326


def test_geometric_centroids_from_polygons():
    polys = gpd.GeoDataFrame(
        {"geoid_bg": ["060730001001"]},
        geometry=[Polygon([(-117.2, 32.7), (-117.1, 32.7), (-117.1, 32.8), (-117.2, 32.8)])],
        crs="EPSG:4326",
    )
    out = geometric_centroids(polys)
    assert out.crs.to_epsg() == 4326
    assert list(out["geoid_bg"]) == ["060730001001"]
    # The centroid lies inside the polygon bounds.
    pt = out.geometry.iloc[0]
    assert -117.2 < pt.x < -117.1
    assert 32.7 < pt.y < 32.8


def test_geometric_centroids_non_contiguous_index():
    # Regression. A filtered, non-contiguous index must not misalign the centroid
    # geometry against the geoid columns and leave NaN coordinates behind.
    import numpy as np

    polys = gpd.GeoDataFrame(
        {"geoid_bg": ["060730001001", "060730001002", "060730001003"]},
        geometry=[
            Polygon([(-117.2, 32.7), (-117.1, 32.7), (-117.1, 32.8), (-117.2, 32.8)]),
            Polygon([(-117.1, 32.7), (-117.0, 32.7), (-117.0, 32.8), (-117.1, 32.8)]),
            Polygon([(-117.0, 32.7), (-116.9, 32.7), (-116.9, 32.8), (-117.0, 32.8)]),
        ],
        crs="EPSG:4326",
    )
    # Drop the middle row so the index becomes [0, 2], non-contiguous.
    out = geometric_centroids(polys.drop(index=1))
    assert len(out) == 2
    assert list(out["geoid_bg"]) == ["060730001001", "060730001003"]
    assert np.isfinite(out.geometry.x).all()
    assert np.isfinite(out.geometry.y).all()
