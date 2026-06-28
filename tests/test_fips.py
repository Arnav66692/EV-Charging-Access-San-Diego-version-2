"""FIPS codes are strings, always, with leading zeros preserved."""

from __future__ import annotations

from src.acquire.acs import parse_matrix
from src.config import fips, load_config


def test_fips_helper_preserves_leading_zeros():
    assert fips(6073) == "06073"
    assert fips("6037") == "06037"
    assert fips("06059") == "06059"
    assert fips(6) == "06"
    assert fips("073") == "073"


def test_fips_helper_returns_strings():
    for value in (6073, "06073", 6, "6"):
        assert isinstance(fips(value), str)


def test_config_county_fips_are_strings_with_zeros():
    cfg = load_config()
    counties = cfg.counties
    assert counties["san_diego"] == "06073"
    assert counties["orange"] == "06059"
    assert counties["los_angeles"] == "06037"
    for code in counties.values():
        assert isinstance(code, str)
        assert code.startswith("0")
        assert len(code) == 5


def test_acs_geoids_are_zero_padded_strings(sample_census_matrix):
    df = parse_matrix(sample_census_matrix)
    # GEOID widths: block group 12, tract 11, county 5.
    assert (df["geoid_bg"].str.len() == 12).all()
    assert (df["geoid_tract"].str.len() == 11).all()
    assert (df["county_fips"].str.len() == 5).all()
    # Leading zeros from the California state code survive.
    assert df["geoid_bg"].str.startswith("06073").all()
    assert df["geoid_tract"].iloc[0] == "06073008339"
    # Every geographic identifier is a string.
    for col in ("geoid_bg", "geoid_tract", "county_fips", "state", "county"):
        assert df[col].map(lambda v: isinstance(v, str)).all()


def test_acs_measures_are_numeric_not_string(sample_census_matrix):
    df = parse_matrix(sample_census_matrix)
    assert df["B01003_001E"].iloc[0] == 1500
    assert str(df["B01003_001E"].dtype).startswith(("int", "float"))
