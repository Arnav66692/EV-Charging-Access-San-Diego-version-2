"""Build the population-weighted 2010 to 2020 crosswalk relationship.

CalEnviroScreen 4.0 is published on 2010 tracts. To assign its percentile to
2020 block groups we need a relationship table weighted by real population, not
land area. Land area weighting is the exact thing this fixes.

The atom is the 2020 Census block. Each 2020 block has a 2020 population, nests
in one 2010 tract, and nests in one 2020 block group. The relationship table sums
2020 block population by the pair of 2010 tract and 2020 block group. That sum is
the weight.

Two official Census bulk inputs are used. Neither needs an API key.

1. 2020 P.L. 94-171 block population. Table P1, field P0010001, the total
   population. The state zip holds a geoheader file and segment files.
   The geoheader gives SUMLEV, LOGRECNO, and the 15 digit block GEOID. Segment 1
   gives the population, keyed by LOGRECNO.

2. The 2010 to 2020 tabulation block relationship file. It maps each 2020 block
   to the 2010 blocks it overlaps, with the land area of the intersection. The
   land area is used only to pick the dominant 2010 tract for a 2020 block, a
   geometry nesting decision. It is never used as a population weight.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import pandas as pd
import requests

from src.config import Config, fips, load_config
from src.utils import ensure_dir, utc_now_iso, write_manifest

REQUEST_TIMEOUT_S = 600

# Census bulk sources. State 06 is California.
PL_ZIP_URL = (
    "https://www2.census.gov/programs-surveys/decennial/2020/data/"
    "01-Redistricting_File--PL_94-171/California/ca2020.pl.zip"
)
BLOCK_REL_ZIP_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/rel2020/t10t20/"
    "TAB2010_TAB2020_ST06.zip"
)

WEIGHT_BASIS = "2020_block_population_P1_001N"

# Field positions in the 2020 P.L. geoheader, pipe delimited, no header row.
GEO_SUMLEV = 2
GEO_LOGRECNO = 7
GEO_BLOCK_GEOID = 9  # 15 digit GEOCODE, state2 county3 tract6 block4
SUMLEV_BLOCK = "750"

# Field positions in P.L. segment 1, pipe delimited, no header row.
SEG_LOGRECNO = 4
SEG_P0010001 = 5  # total population

# Field positions in the 2010 to 2020 block relationship file, pipe delimited.
REL_STATE_2010 = 0
REL_COUNTY_2010 = 1
REL_TRACT_2010 = 2
REL_STATE_2020 = 8
REL_COUNTY_2020 = 9
REL_TRACT_2020 = 10
REL_BLK_2020 = 11
REL_AREALAND_INT = 16


@dataclass(frozen=True)
class RelationshipResult:
    """A built relationship table plus its provenance."""

    df: pd.DataFrame
    weight_basis: str
    total_population: int
    n_block_groups: int


# --- Pure parsers. They take line iterables so they are testable on fixtures. ---

def parse_geoheader_blocks(
    lines: Iterable[str], in_scope_counties: set[str]
) -> dict[str, str]:
    """Map LOGRECNO to the 2020 block GEOID, for in-scope block records only."""
    out: dict[str, str] = {}
    for line in lines:
        f = line.rstrip("\n").split("|")
        if len(f) <= GEO_BLOCK_GEOID or f[GEO_SUMLEV] != SUMLEV_BLOCK:
            continue
        block_geoid = f[GEO_BLOCK_GEOID]
        if len(block_geoid) != 15 or block_geoid[:5] not in in_scope_counties:
            continue
        out[f[GEO_LOGRECNO]] = block_geoid
    return out


def parse_segment1_population(lines: Iterable[str], logrecnos: set[str]) -> dict[str, int]:
    """Map LOGRECNO to total population P0010001, for the wanted LOGRECNOs."""
    out: dict[str, int] = {}
    for line in lines:
        f = line.rstrip("\n").split("|")
        if len(f) <= SEG_P0010001:
            continue
        logrecno = f[SEG_LOGRECNO]
        if logrecno in logrecnos:
            out[logrecno] = int(f[SEG_P0010001])
    return out


def parse_block_to_tract10(
    lines: Iterable[str], in_scope_counties: set[str]
) -> pd.DataFrame:
    """Assign each 2020 block to its dominant 2010 tract by intersection area.

    Returns columns geoid_block_20 and geoid_tract_10. The intersection land area
    is used only to choose the dominant 2010 tract when a 2020 block straddles a
    2010 boundary. It is not a population weight.
    """
    best: dict[str, tuple[float, str]] = {}
    for line in lines:
        f = line.rstrip("\n").split("|")
        if len(f) <= REL_AREALAND_INT:
            continue
        block20 = (
            f[REL_STATE_2020] + f[REL_COUNTY_2020] + f[REL_TRACT_2020] + f[REL_BLK_2020]
        )
        if len(block20) != 15 or block20[:5] not in in_scope_counties:
            continue
        tract10 = f[REL_STATE_2010] + f[REL_COUNTY_2010] + f[REL_TRACT_2010]
        try:
            area_int = float(f[REL_AREALAND_INT] or 0)
        except ValueError:
            area_int = 0.0
        current = best.get(block20)
        if current is None or area_int > current[0]:
            best[block20] = (area_int, tract10)
    rows = [{"geoid_block_20": b, "geoid_tract_10": t} for b, (_, t) in best.items()]
    return pd.DataFrame(rows, columns=["geoid_block_20", "geoid_tract_10"])


# --- Assembly from the parsed atoms. Pure and testable. ---

def build_block_atom_table(
    block_pop: pd.DataFrame, block_to_tract10: pd.DataFrame
) -> pd.DataFrame:
    """Join 2020 block population to its 2010 tract and derive its 2020 bg.

    block_pop needs geoid_block_20 and pop_2020. block_to_tract10 needs
    geoid_block_20 and geoid_tract_10. Returns the atom table with geoid_bg_20
    and geoid_tract_20 derived from the 15 digit block GEOID.
    """
    atom = block_pop.merge(block_to_tract10, on="geoid_block_20", how="inner").copy()
    atom["geoid_block_20"] = atom["geoid_block_20"].astype(str)
    atom["geoid_tract_10"] = atom["geoid_tract_10"].astype(str)
    atom["geoid_bg_20"] = atom["geoid_block_20"].str[:12]
    atom["geoid_tract_20"] = atom["geoid_block_20"].str[:11]
    atom["pop_2020"] = pd.to_numeric(atom["pop_2020"], errors="coerce").fillna(0).astype(int)
    return atom


def build_relationship(atom: pd.DataFrame) -> RelationshipResult:
    """Sum 2020 block population by the 2010 tract and 2020 block group pair.

    Pairs with zero total population are dropped, so every weight is strictly
    positive. The weight is population, recorded in weight_basis.
    """
    grouped = (
        atom.groupby(["geoid_tract_10", "geoid_bg_20"], as_index=False)["pop_2020"]
        .sum()
        .rename(columns={"pop_2020": "pop_overlap"})
    )
    grouped = grouped[grouped["pop_overlap"] > 0].reset_index(drop=True)
    grouped["geoid_tract_20"] = grouped["geoid_bg_20"].str[:11]
    grouped = grouped[
        ["geoid_tract_10", "geoid_tract_20", "geoid_bg_20", "pop_overlap"]
    ]
    grouped.attrs["weight_basis"] = WEIGHT_BASIS
    return RelationshipResult(
        df=grouped,
        weight_basis=WEIGHT_BASIS,
        total_population=int(grouped["pop_overlap"].sum()),
        n_block_groups=int(grouped["geoid_bg_20"].nunique()),
    )


def assert_population_weighted(result: RelationshipResult) -> None:
    """Fail loudly if the weight is not population derived and strictly positive.

    This is the guard against silently reintroducing land area weighting.
    """
    df = result.df
    if "pop_overlap" not in df.columns:
        raise AssertionError("relationship is missing the pop_overlap weight column")
    if result.weight_basis != WEIGHT_BASIS:
        raise AssertionError(
            f"weight_basis is {result.weight_basis!r}, expected {WEIGHT_BASIS!r}. "
            "The weight must be 2020 block population, not land area."
        )
    weights = pd.to_numeric(df["pop_overlap"], errors="coerce")
    if weights.isna().any():
        raise AssertionError("pop_overlap has non numeric values")
    if not (weights > 0).all():
        raise AssertionError("pop_overlap has non positive weights, expected population counts")
    if weights.sum() <= 0:
        raise AssertionError("total population weight is zero")


# --- IO. Streams the large zips line by line. ---

def _download(url: str, dest: Path) -> Path:
    ensure_dir(dest.parent)
    with requests.get(url, stream=True, timeout=REQUEST_TIMEOUT_S) as response:
        response.raise_for_status()
        with open(dest, "wb") as handle:
            for chunk in response.iter_content(chunk_size=1 << 20):
                handle.write(chunk)
    return dest


def _zip_member_lines(zip_path: Path, predicate) -> Iterator[str]:
    """Yield decoded lines from the first member whose name matches predicate."""
    with zipfile.ZipFile(zip_path) as zf:
        name = next(n for n in zf.namelist() if predicate(n))
        with zf.open(name) as raw:
            for line in io.TextIOWrapper(raw, encoding="latin-1"):
                yield line


def load_block_population(pl_zip: Path, in_scope_counties: set[str]) -> pd.DataFrame:
    """Read 2020 block population from the P.L. zip for the in-scope counties."""
    geo_lines = _zip_member_lines(pl_zip, lambda n: n.lower().endswith("geo2020.pl"))
    logrecno_to_block = parse_geoheader_blocks(geo_lines, in_scope_counties)

    seg_lines = _zip_member_lines(pl_zip, lambda n: n.lower().endswith("000012020.pl"))
    logrecno_to_pop = parse_segment1_population(seg_lines, set(logrecno_to_block))

    rows = [
        {"geoid_block_20": block, "pop_2020": logrecno_to_pop.get(logrecno, 0)}
        for logrecno, block in logrecno_to_block.items()
    ]
    return pd.DataFrame(rows, columns=["geoid_block_20", "pop_2020"])


def load_block_to_tract10(rel_zip: Path, in_scope_counties: set[str]) -> pd.DataFrame:
    """Read the 2020 block to dominant 2010 tract assignment from the rel zip."""
    lines = _zip_member_lines(rel_zip, lambda n: n.lower().endswith(".txt"))
    # Skip the header row of the relationship file.
    iterator = iter(lines)
    next(iterator, None)
    return parse_block_to_tract10(iterator, in_scope_counties)


def run(cfg: Config | None = None, keep_downloads: bool = True) -> RelationshipResult:
    """Download the bulk inputs, build the relationship, write it and a manifest.

    Writes data/interim/tract_rel_2010_2020.csv and a manifest recording the
    population weight basis. The CSV feeds src/acquire/ces_crosswalk.py.
    """
    cfg = cfg or load_config()
    in_scope = {fips(c) for c in cfg.all_county_fips}
    raw = ensure_dir(cfg.path("raw"))

    pl_zip = raw / "ca2020.pl.zip"
    rel_zip = raw / "TAB2010_TAB2020_ST06.zip"
    if not pl_zip.exists():
        _download(PL_ZIP_URL, pl_zip)
    if not rel_zip.exists():
        _download(BLOCK_REL_ZIP_URL, rel_zip)

    block_pop = load_block_population(pl_zip, in_scope)
    block_to_tract10 = load_block_to_tract10(rel_zip, in_scope)
    atom = build_block_atom_table(block_pop, block_to_tract10)
    result = build_relationship(atom)
    assert_population_weighted(result)

    interim = ensure_dir(cfg.path("interim"))
    out_path = interim / "tract_rel_2010_2020.csv"
    result.df.to_csv(out_path, index=False)

    manifest = {
        "source": "Census 2020 P.L. 94-171 block population and 2010 to 2020 block relationship",
        "pl_zip_url": PL_ZIP_URL,
        "block_relationship_url": BLOCK_REL_ZIP_URL,
        "weight_basis": result.weight_basis,
        "weighting": "population",
        "atom": "2020 census block",
        "in_scope_counties": sorted(in_scope),
        "total_population": result.total_population,
        "n_block_groups": result.n_block_groups,
        "n_pairs": int(len(result.df)),
        "built_at_utc": utc_now_iso(),
        "license": "Public domain, U.S. Census Bureau.",
        "redistributable": True,
    }
    write_manifest(cfg.path("manifests") / "ces_relationship.manifest.json", manifest)

    if not keep_downloads:
        pl_zip.unlink(missing_ok=True)
        rel_zip.unlink(missing_ok=True)

    print(
        f"Relationship built. {result.n_block_groups} block groups, "
        f"{len(result.df)} tract-to-bg pairs, weight basis {result.weight_basis}, "
        f"total pop {result.total_population}"
    )
    return result


if __name__ == "__main__":
    run()
