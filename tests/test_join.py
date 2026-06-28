"""The candidate to grid join leaves zero candidates silently unjoined."""

from __future__ import annotations

import pandas as pd

from src.join.candidate_grid_join import nearest_join_within


def test_every_candidate_is_accounted_for(sample_candidates, sample_grid):
    result = nearest_join_within(
        sample_candidates,
        sample_grid,
        max_distance_m=500.0,
        working_crs="EPSG:3310",
        storage_crs="EPSG:4326",
    )
    # No candidate is dropped.
    assert len(result) == len(sample_candidates)
    assert set(result["candidate_id"]) == set(sample_candidates["candidate_id"])
    # joined_flag is always a real boolean, never missing. No silent gaps.
    assert result["joined_flag"].notna().all()
    assert result["joined_flag"].map(lambda v: isinstance(v, bool)).all()


def test_joined_and_unjoined_partition_the_set(sample_candidates, sample_grid):
    result = nearest_join_within(
        sample_candidates, sample_grid, 500.0, "EPSG:3310", "EPSG:4326"
    )
    joined = result[result["joined_flag"]]
    unjoined = result[~result["joined_flag"]]
    assert len(joined) + len(unjoined) == len(result)
    # The three near candidates join, the far one does not.
    assert len(joined) == 3
    assert len(unjoined) == 1
    assert unjoined["candidate_id"].iloc[0] == "osm:node/4"


def test_capacity_carried_only_for_joined(sample_candidates, sample_grid):
    result = nearest_join_within(
        sample_candidates, sample_grid, 500.0, "EPSG:3310", "EPSG:4326"
    )
    joined = result[result["joined_flag"]]
    unjoined = result[~result["joined_flag"]]
    # Joined candidates carry the section capacity.
    assert (joined["load_capacity_mw"] == 3.5).all()
    assert joined["snap_distance_m"].notna().all()
    # Unjoined candidates carry no capacity and no distance.
    assert unjoined["load_capacity_mw"].isna().all()
    assert unjoined["snap_distance_m"].isna().all()


def test_threshold_controls_joining(sample_candidates, sample_grid):
    # With a one meter threshold even the near candidates fall out, but they are
    # still reported as unjoined rather than dropped.
    result = nearest_join_within(
        sample_candidates, sample_grid, 1.0, "EPSG:3310", "EPSG:4326"
    )
    assert len(result) == len(sample_candidates)
    assert result["joined_flag"].notna().all()
    assert not result["joined_flag"].any()


def test_empty_grid_flags_all_unjoined(sample_candidates, sample_grid):
    empty_grid = sample_grid.iloc[0:0]
    result = nearest_join_within(
        sample_candidates, empty_grid, 500.0, "EPSG:3310", "EPSG:4326"
    )
    assert len(result) == len(sample_candidates)
    assert result["joined_flag"].notna().all()
    assert not result["joined_flag"].any()
