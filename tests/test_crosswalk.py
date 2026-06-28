"""The CES crosswalk assigns a DAC percentile to 100 percent of in-scope block
groups, or the gap is listed explicitly. There is never a silent gap."""

from __future__ import annotations

import pandas as pd
import pytest

from src.acquire.ces_crosswalk import (
    assign_to_block_groups,
    build_blockgroup_crosswalk,
    build_tract_crosswalk,
    coverage_report,
)
from src.acquire.ces_relationship import (
    WEIGHT_BASIS,
    RelationshipResult,
    assert_population_weighted,
    build_block_atom_table,
    build_relationship,
    parse_block_to_tract10,
    parse_geoheader_blocks,
    parse_segment1_population,
)


def test_population_weighted_crosswalk(sample_ces, sample_relationship):
    tract20 = build_tract_crosswalk(sample_ces, sample_relationship)
    by_tract = tract20.set_index("geoid_tract_20")

    # Identity tract keeps its own percentile and is not flagged crosswalked.
    assert by_tract.loc["06073008339", "ces_percentile"] == 80.0
    assert bool(by_tract.loc["06073008339", "crosswalked"]) is False

    # Merged 2020 tract is the population weighted mean of its two 2010 parents.
    # (40 * 600 + 90 * 1400) / 2000 == 75.0
    assert by_tract.loc["06073008342", "ces_percentile"] == 75.0
    assert bool(by_tract.loc["06073008342", "crosswalked"]) is True


def test_dac_flag_and_exclude_flag(sample_ces, sample_relationship, sample_blockgroups_2020):
    tract20 = build_tract_crosswalk(sample_ces, sample_relationship)
    assigned = assign_to_block_groups(tract20, sample_blockgroups_2020, threshold=75.0)
    by_bg = assigned.set_index("geoid_bg")

    # Percentile 80 and 75 are both at or above the 75 threshold.
    assert bool(by_bg.loc["060730083391", "dac_flag"]) is True
    assert bool(by_bg.loc["060730083421", "dac_flag"]) is True
    # The crosswalked block group carries the exclude flag for the sensitivity run.
    assert bool(by_bg.loc["060730083391", "exclude_crosswalked"]) is False
    assert bool(by_bg.loc["060730083421", "exclude_crosswalked"]) is True


def test_full_coverage_reported(sample_ces, sample_relationship, sample_blockgroups_2020):
    tract20 = build_tract_crosswalk(sample_ces, sample_relationship)
    assigned = assign_to_block_groups(tract20, sample_blockgroups_2020, threshold=75.0)
    in_scope = sample_blockgroups_2020["geoid_bg"].tolist()
    report = coverage_report(assigned, in_scope)

    assert report.coverage_fraction == 1.0
    assert report.is_complete
    assert report.missing_geoids == ()


def test_gap_is_listed_never_silent(sample_ces, sample_relationship, sample_blockgroups_2020):
    # Add a block group whose tract is not in the crosswalk at all.
    extra = pd.concat(
        [
            sample_blockgroups_2020,
            pd.DataFrame(
                {"geoid_bg": ["060730099991"], "geoid_tract": ["06073009999"]}
            ),
        ],
        ignore_index=True,
    )
    tract20 = build_tract_crosswalk(sample_ces, sample_relationship)
    assigned = assign_to_block_groups(tract20, extra, threshold=75.0)
    report = coverage_report(assigned, extra["geoid_bg"].tolist())

    # Coverage is below 100 percent, but the missing block group is named, and
    # covered plus missing accounts for every in-scope block group.
    assert report.coverage_fraction < 1.0
    assert "060730099991" in report.missing_geoids
    assert report.is_complete


# --- Population-weighted relationship helper. The weight must be real
# --- population, never land area. ---


def test_relationship_weight_is_population_not_area(
    sample_block_pop, sample_block_to_tract10
):
    atom = build_block_atom_table(sample_block_pop, sample_block_to_tract10)
    result = build_relationship(atom)

    # The weight basis is recorded as 2020 block population, not area.
    assert result.weight_basis == WEIGHT_BASIS
    assert "population" in WEIGHT_BASIS

    # The weight column equals summed 2020 block population.
    by_pair = result.df.set_index(["geoid_tract_10", "geoid_bg_20"])["pop_overlap"]
    assert by_pair.loc[("06073008339", "060730083391")] == 1500  # 800 + 700
    assert by_pair.loc[("06073008340", "060730083421")] == 600
    assert by_pair.loc[("06073008341", "060730083421")] == 1400
    assert result.total_population == 3500

    # The guard passes for real population weights.
    assert_population_weighted(result)


def test_assert_population_weighted_rejects_bad_basis(
    sample_block_pop, sample_block_to_tract10
):
    atom = build_block_atom_table(sample_block_pop, sample_block_to_tract10)
    good = build_relationship(atom)

    # A relationship tagged with an area basis must be rejected.
    area_tagged = RelationshipResult(
        df=good.df, weight_basis="land_area", total_population=good.total_population,
        n_block_groups=good.n_block_groups,
    )
    with pytest.raises(AssertionError):
        assert_population_weighted(area_tagged)


def test_assert_population_weighted_rejects_nonpositive_weight(
    sample_block_pop, sample_block_to_tract10
):
    atom = build_block_atom_table(sample_block_pop, sample_block_to_tract10)
    good = build_relationship(atom)
    bad_df = good.df.copy()
    bad_df.loc[0, "pop_overlap"] = 0
    bad = RelationshipResult(
        df=bad_df, weight_basis=WEIGHT_BASIS, total_population=int(bad_df["pop_overlap"].sum()),
        n_block_groups=good.n_block_groups,
    )
    with pytest.raises(AssertionError):
        assert_population_weighted(bad)


def test_relationship_drops_zero_population_pairs(
    sample_block_pop, sample_block_to_tract10
):
    # A block with zero population must not create a weighted pair.
    pop = pd.concat(
        [
            sample_block_pop,
            pd.DataFrame({"geoid_block_20": ["060730083431000"], "pop_2020": [0]}),
        ],
        ignore_index=True,
    )
    mapping = pd.concat(
        [
            sample_block_to_tract10,
            pd.DataFrame(
                {"geoid_block_20": ["060730083431000"], "geoid_tract_10": ["06073008343"]}
            ),
        ],
        ignore_index=True,
    )
    atom = build_block_atom_table(pop, mapping)
    result = build_relationship(atom)
    assert (result.df["pop_overlap"] > 0).all()
    # The zero-population block group is dropped, not carried as a zero weight.
    assert "060730083431" not in set(result.df["geoid_bg_20"])


# --- Block-group level crosswalk, the precise path. ---


def test_blockgroup_crosswalk_is_population_weighted(sample_ces, sample_bg_relationship):
    assigned = build_blockgroup_crosswalk(sample_ces, sample_bg_relationship, threshold=75.0)
    by_bg = assigned.set_index("geoid_bg")

    # Identity block group keeps its tract percentile.
    assert by_bg.loc["060730083391", "ces_percentile"] == 80.0
    assert bool(by_bg.loc["060730083391", "exclude_crosswalked"]) is False

    # The crosswalked block group is the population weighted mean of its two
    # contributing 2010 tracts. (40 * 600 + 90 * 1400) / 2000 == 75.0
    assert by_bg.loc["060730083421", "ces_percentile"] == 75.0
    assert bool(by_bg.loc["060730083421", "exclude_crosswalked"]) is True
    assert bool(by_bg.loc["060730083421", "dac_flag"]) is True


def test_blockgroup_crosswalk_full_coverage(
    sample_ces, sample_bg_relationship, sample_blockgroups_2020
):
    assigned = build_blockgroup_crosswalk(sample_ces, sample_bg_relationship, threshold=75.0)
    report = coverage_report(assigned, sample_blockgroups_2020["geoid_bg"].tolist())
    assert report.coverage_fraction == 1.0
    assert report.is_complete
    assert report.missing_geoids == ()


# --- Bulk file parsers, validated on the real Census pipe-delimited layout. ---


def test_parse_geoheader_blocks_filters_blocks_and_counties():
    lines = [
        # SUMLEV 750 block in San Diego county, in scope.
        "PLST|CA|750|00|00|000|00|0000010|7500000US060730083391000|060730083391000|x",
        # SUMLEV 040 state record, not a block, skipped.
        "PLST|CA|040|00|00|000|00|0000001|0400000US06|06|x",
        # SUMLEV 750 block in an out of scope county 06001, skipped.
        "PLST|CA|750|00|00|000|00|0000020|7500000US060010001001000|060010001001000|x",
    ]
    out = parse_geoheader_blocks(lines, {"06073", "06059", "06037"})
    assert out == {"0000010": "060730083391000"}


def test_parse_segment1_population_picks_total_pop():
    lines = [
        "PLST|CA|000|01|0000010|123|999|0",
        "PLST|CA|000|01|0000020|456|999|0",
    ]
    out = parse_segment1_population(lines, {"0000010"})
    assert out == {"0000010": 123}


def test_parse_block_to_tract10_uses_area_only_for_assignment():
    # The same 2020 block straddles two 2010 tracts. Area chooses the dominant
    # 2010 tract for assignment. Area is never used as a population weight.
    f = ["06", "073", "008340", "1000", "", "0", "0", "p",
         "06", "073", "008342", "1000", "", "0", "0", "p", "300", "0"]
    g = ["06", "073", "008341", "1000", "", "0", "0", "p",
         "06", "073", "008342", "1000", "", "0", "0", "p", "900", "0"]
    lines = ["|".join(f), "|".join(g)]
    out = parse_block_to_tract10(lines, {"06073"})
    # One row for the 2020 block, assigned to the larger-area 2010 tract ...341.
    assert len(out) == 1
    assert out.iloc[0]["geoid_block_20"] == "060730083421000"
    assert out.iloc[0]["geoid_tract_10"] == "06073008341"
