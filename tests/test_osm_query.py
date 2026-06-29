"""Regression guard for the Overpass county query.

County names like Orange County are not unique across the United States. An
unscoped name match pulled in parking lots from other states, so the query must
scope the county within California first.
"""

from __future__ import annotations

from src.acquire.osm_osrm import COUNTY_OSM_NAME, build_overpass_query


def test_query_scopes_county_within_california():
    q = build_overpass_query("Orange County", 120)
    # California is the outer scope.
    assert '"admin_level"="4"' in q
    assert '"name"="California"' in q
    # The county is selected within that California area and mapped to an area.
    assert "rel(area.ca)" in q
    assert "map_to_area" in q
    assert '"name"="Orange County"' in q


def test_all_in_scope_counties_have_osm_names():
    # Every in-scope county FIPS maps to the administrative name OSM uses.
    assert COUNTY_OSM_NAME["06073"] == "San Diego County"
    assert COUNTY_OSM_NAME["06059"] == "Orange County"
    assert COUNTY_OSM_NAME["06037"] == "Los Angeles County"
