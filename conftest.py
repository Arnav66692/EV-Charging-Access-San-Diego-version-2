"""Pytest configuration and shared fixtures.

Placing this at the repo root puts the root on sys.path, so tests import the
src package directly. Fixtures build small in-memory datasets so the suite runs
fully offline and deterministically.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, Point

REPO_ROOT = Path(__file__).resolve().parent


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
