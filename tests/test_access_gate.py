"""The v1-compat gate runs end to end on fixtures and emits a result. Centroid
parsing works on the centers of population format."""

from __future__ import annotations

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


def test_exact_reproduction_path_with_reference_ratio(gate_fixture):
    # When a v1 snapshot path and reference ratio are supplied, the gate compares
    # the recomputed ratio to the reference within tolerance.
    first = run_gate(
        origins=gate_fixture["origins"],
        supplies_dcfc=gate_fixture["supplies_dcfc"],
        residential=gate_fixture["residential"],
        dac_flags=gate_fixture["dac_flags"],
        population=gate_fixture["population"],
        radius_m=gate_fixture["radius_m"],
    )
    computed = first.sfca_dac_ratio
    result = run_gate(
        origins=gate_fixture["origins"],
        supplies_dcfc=gate_fixture["supplies_dcfc"],
        residential=gate_fixture["residential"],
        dac_flags=gate_fixture["dac_flags"],
        population=gate_fixture["population"],
        radius_m=gate_fixture["radius_m"],
        v1_snapshot_path="/some/v1/snapshot.json",
        v1_reference_ratio=computed,
        tolerance=0.01,
    )
    assert result.path_taken == "exact_reproduction"
    assert result.passed is True


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
