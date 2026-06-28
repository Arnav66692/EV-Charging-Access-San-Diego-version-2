"""Pytest configuration and shared fixtures.

Placing this at the repo root puts the root on sys.path, so tests import the
src package directly. Fixtures build small in-memory datasets so the suite runs
fully offline and deterministically.
"""

from __future__ import annotations

import math
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, Point

REPO_ROOT = Path(__file__).resolve().parent

# Rough meters-per-degree near San Diego, for building geometry fixtures.
_M_PER_DEG_LAT = 110900.0
_M_PER_DEG_LON = 93660.0  # at about 32.7 degrees north


def _offset(base_lon: float, base_lat: float, east_m: float, north_m: float) -> Point:
    """A point offset east and north of a base, in meters, near San Diego."""
    return Point(base_lon + east_m / _M_PER_DEG_LON, base_lat + north_m / _M_PER_DEG_LAT)


@pytest.fixture
def sample_afdc_raw() -> dict:
    """A minimal AFDC style payload covering DCFC only, L2 only, and both."""
    return {
        "total_results": 3,
        "fuel_stations": [
            {
                "id": 1001,
                "station_name": "Both Ports Site",
                "latitude": 32.7157,
                "longitude": -117.1611,
                "ev_network": "ChargePoint Network",
                "access_code": "public",
                "ev_dc_fast_num": 4,
                "ev_level2_evse_num": 8,
                "ev_connector_types": ["CHADEMO", "J1772COMBO"],
            },
            {
                "id": 1002,
                "station_name": "L2 Only Site",
                "latitude": 33.6846,
                "longitude": -117.8265,
                "ev_network": "EV Connect",
                "access_code": "public",
                "ev_dc_fast_num": None,
                "ev_level2_evse_num": 6,
                "ev_connector_types": ["J1772"],
            },
            {
                "id": 1003,
                "station_name": "DCFC Only Site",
                "latitude": 34.0560,
                "longitude": -118.2368,
                "ev_network": "Tesla",
                "access_code": "public",
                "ev_dc_fast_num": 12,
                "ev_level2_evse_num": None,
                "ev_connector_types": ["TESLA"],
            },
        ],
    }


@pytest.fixture
def sample_census_matrix() -> list[list[str]]:
    """A Census API style matrix for two block groups in San Diego County.

    The geographic components carry the leading zeros that must survive parsing.
    """
    return [
        ["NAME", "B01003_001E", "B25003_001E", "B25003_002E", "state", "county", "tract", "block group"],
        ["Block Group 1", "1500", "600", "350", "06", "073", "008339", "1"],
        ["Block Group 2", "1200", "500", "200", "06", "073", "008339", "2"],
    ]


@pytest.fixture
def sample_candidates() -> gpd.GeoDataFrame:
    """Candidate points near and far from the sample grid line.

    Three candidates sit within a few hundred meters of the grid line. One sits
    far away, well beyond any sane snap threshold, to exercise the unjoined path.
    """
    rows = [
        {"candidate_id": "osm:node/1", "county_fips": "06073", "facility_type": "parking"},
        {"candidate_id": "osm:node/2", "county_fips": "06073", "facility_type": "retail"},
        {"candidate_id": "osm:node/3", "county_fips": "06073", "facility_type": "civic"},
        {"candidate_id": "osm:node/4", "county_fips": "06073", "facility_type": "parking"},
    ]
    geoms = [
        Point(-117.1610, 32.7157),  # ~10 m from the line
        Point(-117.1605, 32.7158),  # ~50 m from the line
        Point(-117.1600, 32.7159),  # ~100 m from the line
        Point(-116.5000, 33.5000),  # far away, must be unjoined
    ]
    return gpd.GeoDataFrame(rows, geometry=geoms, crs="EPSG:4326")


@pytest.fixture
def sample_grid() -> gpd.GeoDataFrame:
    """A single grid line section near downtown San Diego with a capacity value."""
    line = LineString([(-117.1615, 32.7150), (-117.1615, 32.7170)])
    return gpd.GeoDataFrame(
        [{"load_capacity_mw": 3.5, "generation_limiting_factor": "Generation - Thermal"}],
        geometry=[line],
        crs="EPSG:4326",
    )


@pytest.fixture
def sample_ces() -> pd.DataFrame:
    """CES 4.0 percentiles on 2010 tracts."""
    return pd.DataFrame(
        {
            "geoid_tract_10": ["06073008339", "06073008340", "06073008341"],
            "ces_percentile": [80.0, 40.0, 90.0],
        }
    )


@pytest.fixture
def sample_relationship() -> pd.DataFrame:
    """2010 to 2020 tract relationship with population overlap weights.

    Tract ...339 is an identity match. Tract ...342 is a 2020 tract formed from
    two 2010 tracts, so it is a real crosswalk weighted by population.
    """
    return pd.DataFrame(
        {
            "geoid_tract_10": ["06073008339", "06073008340", "06073008341"],
            "geoid_tract_20": ["06073008339", "06073008342", "06073008342"],
            "pop_overlap": [1500.0, 600.0, 1400.0],
        }
    )


@pytest.fixture
def sample_block_pop() -> pd.DataFrame:
    """2020 block population. Two blocks per block group.

    Block GEOID is 15 digits, state2 county3 tract6 block4. The block group is
    the first 12 digits. These nest into the same 2020 tracts as the other CES
    fixtures.
    """
    return pd.DataFrame(
        {
            "geoid_block_20": [
                "060730083391000",
                "060730083391001",
                "060730083421000",
                "060730083421001",
            ],
            "pop_2020": [800, 700, 600, 1400],
        }
    )


@pytest.fixture
def sample_block_to_tract10() -> pd.DataFrame:
    """Each 2020 block assigned to its dominant 2010 tract.

    The block group ...3421 is a real crosswalk. Its two blocks come from two
    different 2010 tracts, ...340 and ...341.
    """
    return pd.DataFrame(
        {
            "geoid_block_20": [
                "060730083391000",
                "060730083391001",
                "060730083421000",
                "060730083421001",
            ],
            "geoid_tract_10": [
                "06073008339",
                "06073008339",
                "06073008340",
                "06073008341",
            ],
        }
    )


@pytest.fixture
def sample_bg_relationship() -> pd.DataFrame:
    """Block group level relationship weighted by 2020 block population.

    ...3391 is identity, one 2010 tract equal to its own 2020 tract.
    ...3421 draws from two 2010 tracts, weights 600 and 1400.
    """
    return pd.DataFrame(
        {
            "geoid_tract_10": [
                "06073008339",
                "06073008339",
                "06073008340",
                "06073008341",
            ],
            "geoid_tract_20": [
                "06073008339",
                "06073008339",
                "06073008342",
                "06073008342",
            ],
            "geoid_bg_20": [
                "060730083391",
                "060730083392",
                "060730083421",
                "060730083421",
            ],
            "pop_overlap": [1500, 1200, 600, 1400],
        }
    )


@pytest.fixture
def sample_blockgroups_2020() -> pd.DataFrame:
    """2020 block groups nested in the crosswalked 2020 tracts."""
    return pd.DataFrame(
        {
            "geoid_bg": [
                "060730083391",
                "060730083392",
                "060730083421",
            ],
            "geoid_tract": [
                "06073008339",
                "06073008339",
                "06073008342",
            ],
        }
    )


# --- Phase 2 accessibility fixtures. ---

from src.access.od_types import ODStructure  # noqa: E402


@pytest.fixture
def e2_params() -> dict:
    return {"zone_breaks": [0.3333, 0.6667, 1.0], "zone_weights": [1.0, 0.68, 0.22]}


@pytest.fixture
def sfca_toy() -> dict:
    """A 3-station, 4-block-group toy with all in-catchment costs at 0.

    With cost 0 every decay weight is 1, so the math reduces to the two step
    gravity core. That isolates the supply demand ratio and the Huff allocation,
    which is the substantive part to hand check. Reachability:
      b1 reaches s1, s2
      b2 reaches s1, s2, s3
      b3 reaches s2, s3
      b4 reaches s3
    """
    pairs = pd.DataFrame(
        {
            "origin_id": ["b1", "b1", "b2", "b2", "b2", "b3", "b3", "b4"],
            "supply_id": ["s1", "s2", "s1", "s2", "s3", "s2", "s3", "s3"],
            "cost": [0.0] * 8,
        }
    )
    return {
        "od": ODStructure(pairs=pairs, cost_unit="minutes", threshold=15.0, backend="test"),
        "supply": pd.Series({"s1": 4.0, "s2": 2.0, "s3": 6.0}),
        "demand": pd.Series({"b1": 100.0, "b2": 200.0, "b3": 300.0, "b4": 400.0}),
        "all_origins": ["b1", "b2", "b3", "b4"],
    }


@pytest.fixture
def gate_fixture() -> dict:
    """A San Diego style fixture engineered to show the proximity reversal.

    DAC block groups sit very close to a small, contested DCFC station. Non DAC
    block groups sit farther from a large, uncontested station. Nearest distance
    flatters the DAC areas. SFCA, which accounts for supply and competition,
    reveals the DAC areas have lower access. The two clusters are far enough
    apart that neither reaches the other within the DCFC radius.
    """
    s_a = (-117.10, 32.70)  # small station, capacity 2, by the DAC cluster
    s_b = (-117.20, 32.75)  # large station, capacity 20, by the non DAC cluster

    origins = gpd.GeoDataFrame(
        {
            "origin_id": [
                "060730001001",
                "060730001002",
                "060730001003",
                "060730002001",
                "060730002002",
            ],
            "geoid_bg": [
                "060730001001",
                "060730001002",
                "060730001003",
                "060730002001",
                "060730002002",
            ],
        },
        geometry=[
            _offset(*s_a, 200, 0),    # DAC, 200 m from small station
            _offset(*s_a, 0, 200),    # DAC
            _offset(*s_a, -200, 0),   # DAC
            _offset(*s_b, 800, 0),    # non DAC, 800 m from large station
            _offset(*s_b, 0, -800),   # non DAC
        ],
        crs="EPSG:4326",
    )
    supplies_dcfc = gpd.GeoDataFrame(
        {"supply_id": ["sA", "sB"], "capacity": [2.0, 20.0]},
        geometry=[Point(*s_a), Point(*s_b)],
        crs="EPSG:4326",
    )
    residential = pd.Series(
        {
            "060730001001": 1000.0,
            "060730001002": 1000.0,
            "060730001003": 1000.0,
            "060730002001": 1000.0,
            "060730002002": 1000.0,
        }
    )
    dac_flags = pd.Series(
        {
            "060730001001": True,
            "060730001002": True,
            "060730001003": True,
            "060730002001": False,
            "060730002002": False,
        },
        dtype="boolean",
    )
    radius_m = 6.0 * 1609.344  # v1 DCFC radius, 6 miles
    return {
        "origins": origins,
        "supplies_dcfc": supplies_dcfc,
        "residential": residential,
        "dac_flags": dac_flags,
        "population": residential,
        "radius_m": radius_m,
    }
