"""CalEnviroScreen 4.0 disadvantaged community crosswalk.

CES 4.0 is published on 2010 census tracts. This module crosswalks it to 2020
tracts using a Census 2010 to 2020 relationship table, weighted by population,
not land area. The 2020 tract percentile is then assigned to every 2020 block
group nested in that tract. A community is flagged disadvantaged when its
percentile is at or above the configured threshold, default 75.

An exclude_crosswalked flag marks block groups whose value came from a real
crosswalk rather than an identity match, so a later sensitivity run can drop
them. Coverage is reported. The target is 100 percent of in-scope block groups.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.config import Config, load_config
from src.utils import ensure_dir, utc_now_iso, write_manifest


# Column names this module produces internally.
COL_TRACT10 = "geoid_tract_10"
COL_TRACT20 = "geoid_tract_20"
COL_POP = "pop_overlap"
COL_PCTL = "ces_percentile"
COL_BG = "geoid_bg_20"


@dataclass(frozen=True)
class CoverageReport:
    """Coverage of the DAC assignment over in-scope block groups."""

    total_in_scope: int
    covered: int
    missing_geoids: tuple[str, ...]

    @property
    def coverage_fraction(self) -> float:
        if self.total_in_scope == 0:
            return 1.0
        return self.covered / self.total_in_scope

    @property
    def is_complete(self) -> bool:
        # Complete when every in-scope block group is either covered or the gap
        # is explicitly listed. There is never a silent gap.
        return self.covered + len(self.missing_geoids) == self.total_in_scope


def build_tract_crosswalk(ces_df: pd.DataFrame, rel_df: pd.DataFrame) -> pd.DataFrame:
    """Population weight CES 2010 tract percentiles onto 2020 tracts.

    ces_df needs columns geoid_tract_10 and ces_percentile.
    rel_df needs columns geoid_tract_10, geoid_tract_20, pop_overlap.

    The percentile is an intensive measure, so each 2020 tract gets the
    population weighted mean of the overlapping 2010 tract percentiles. A
    crosswalked flag is True when the 2020 tract is not a clean identity match
    to a single 2010 tract of the same GEOID.
    """
    merged = rel_df.merge(ces_df[[COL_TRACT10, COL_PCTL]], on=COL_TRACT10, how="left")
    merged[COL_POP] = pd.to_numeric(merged[COL_POP], errors="coerce").fillna(0.0)

    # Only overlaps that carry a CES percentile contribute to the weighted mean.
    valid = merged[merged[COL_PCTL].notna()].copy()
    valid["_weighted"] = valid[COL_PCTL] * valid[COL_POP]

    grouped = valid.groupby(COL_TRACT20)
    weight_sum = grouped[COL_POP].sum()
    weighted_pctl = grouped["_weighted"].sum() / weight_sum.where(weight_sum > 0)
    # Where no population weight exists, fall back to a plain mean of percentiles.
    mean_pctl = grouped[COL_PCTL].mean()
    final_pctl = weighted_pctl.fillna(mean_pctl)

    contributors = grouped[COL_TRACT10].agg(lambda s: list(pd.unique(s)))

    out = pd.DataFrame(
        {
            COL_TRACT20: final_pctl.index.astype(str),
            COL_PCTL: pd.to_numeric(final_pctl.values, errors="coerce"),
        }
    )
    out["crosswalked"] = [
        not (len(contributors[t]) == 1 and str(contributors[t][0]) == str(t))
        for t in out[COL_TRACT20]
    ]
    return out.reset_index(drop=True)


def assign_to_block_groups(
    tract20_df: pd.DataFrame,
    block_groups: pd.DataFrame,
    threshold: float,
) -> pd.DataFrame:
    """Assign 2020 tract percentiles to 2020 block groups and flag DAC status.

    block_groups needs columns geoid_bg and geoid_tract. Every block group in a
    tract inherits that tract's percentile. The DAC flag is percentile at or
    above the threshold.
    """
    bg = block_groups[["geoid_bg", "geoid_tract"]].copy()
    bg["geoid_bg"] = bg["geoid_bg"].astype(str)
    bg["geoid_tract"] = bg["geoid_tract"].astype(str)

    lut = tract20_df.rename(columns={COL_TRACT20: "geoid_tract"}).copy()
    lut["geoid_tract"] = lut["geoid_tract"].astype(str)

    joined = bg.merge(
        lut[["geoid_tract", COL_PCTL, "crosswalked"]], on="geoid_tract", how="left"
    )
    # Use a nullable boolean so a missing percentile stays NA rather than a
    # misleading False. A block group with no percentile is unknown, not non-DAC.
    dac = pd.Series(pd.NA, index=joined.index, dtype="boolean")
    has_pctl = joined[COL_PCTL].notna()
    dac[has_pctl] = joined.loc[has_pctl, COL_PCTL] >= threshold
    joined["dac_flag"] = dac
    joined = joined.rename(columns={"crosswalked": "exclude_crosswalked"})
    return joined


def coverage_report(assigned: pd.DataFrame, in_scope_bg: list[str]) -> CoverageReport:
    """Report how many in-scope block groups received a percentile."""
    in_scope = [str(g) for g in in_scope_bg]
    have = assigned.loc[assigned[COL_PCTL].notna(), "geoid_bg"].astype(str)
    have_set = set(have)
    missing = tuple(sorted(g for g in in_scope if g not in have_set))
    covered = len(in_scope) - len(missing)
    return CoverageReport(
        total_in_scope=len(in_scope), covered=covered, missing_geoids=missing
    )


def build_blockgroup_crosswalk(
    ces_df: pd.DataFrame, rel_df: pd.DataFrame, threshold: float
) -> pd.DataFrame:
    """Population weight CES 2010 tract percentiles directly onto 2020 block groups.

    This is the precise path. It uses a block group level relationship built from
    2020 block population, so a block group that draws from more than one 2010
    tract gets a true population weighted percentile, not a tract level inherited
    one.

    ces_df needs geoid_tract_10 and ces_percentile. rel_df needs geoid_tract_10,
    geoid_bg_20, and pop_overlap, where pop_overlap is summed 2020 block
    population. See src/acquire/ces_relationship.py.

    Returns geoid_bg, geoid_tract, ces_percentile, dac_flag, exclude_crosswalked.
    """
    merged = rel_df.merge(ces_df[[COL_TRACT10, COL_PCTL]], on=COL_TRACT10, how="left")
    merged[COL_POP] = pd.to_numeric(merged[COL_POP], errors="coerce").fillna(0.0)

    valid = merged[merged[COL_PCTL].notna()].copy()
    valid["_weighted"] = valid[COL_PCTL] * valid[COL_POP]

    grouped = valid.groupby(COL_BG)
    weight_sum = grouped[COL_POP].sum()
    weighted_pctl = grouped["_weighted"].sum() / weight_sum.where(weight_sum > 0)
    mean_pctl = grouped[COL_PCTL].mean()
    final_pctl = weighted_pctl.fillna(mean_pctl)

    contributors = grouped[COL_TRACT10].agg(lambda s: list(pd.unique(s)))

    out = pd.DataFrame(
        {
            "geoid_bg": final_pctl.index.astype(str),
            COL_PCTL: pd.to_numeric(final_pctl.values, errors="coerce"),
        }
    )
    out["geoid_tract"] = out["geoid_bg"].str[:11]
    # A block group is identity, not crosswalked, only when all of its population
    # maps to one 2010 tract whose GEOID equals its own 2020 tract.
    out["exclude_crosswalked"] = [
        not (len(contributors[bg]) == 1 and str(contributors[bg][0]) == bg[:11])
        for bg in out["geoid_bg"]
    ]

    dac = pd.Series(pd.NA, index=out.index, dtype="boolean")
    has_pctl = out[COL_PCTL].notna()
    dac[has_pctl] = out.loc[has_pctl, COL_PCTL] >= threshold
    out["dac_flag"] = dac

    return out[["geoid_bg", "geoid_tract", COL_PCTL, "dac_flag", "exclude_crosswalked"]]


# --- IO oriented helpers used by run, kept separate from the pure functions. ---

def load_ces(path: Path) -> pd.DataFrame:
    """Load CES 4.0 from an OEHHA xlsx or csv into a tidy 2010 tract table.

    The CES 4.0 release uses a Census Tract column of 2010 GEOIDs and a
    CES 4.0 Percentile column. Column names are matched case insensitively.
    """
    if path.suffix.lower() in (".xlsx", ".xls"):
        raw = pd.read_excel(path)
    else:
        raw = pd.read_csv(path)
    cols = {c.lower().strip(): c for c in raw.columns}

    def pick(*candidates: str) -> str:
        for cand in candidates:
            if cand in cols:
                return cols[cand]
        raise KeyError(f"None of {candidates} found in CES columns {list(raw.columns)}")

    tract_col = pick("census tract", "tract", "geoid", "ctidfp00")
    pctl_col = pick("ces 4.0 percentile", "ces 4.0 percentile range", "cespct", "percentile")
    out = pd.DataFrame(
        {
            COL_TRACT10: raw[tract_col].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(11),
            COL_PCTL: pd.to_numeric(raw[pctl_col], errors="coerce"),
        }
    )
    return out.dropna(subset=[COL_PCTL])


def run(cfg: Config | None = None) -> CoverageReport:
    """End to end CES crosswalk over the in-scope ACS block groups.

    Expects:
      data/raw/ces40.xlsx or .csv                 CES 4.0 from OEHHA
      data/interim/tract_rel_2010_2020.csv        population weighted relationship,
                                                  geoid_tract_10, geoid_tract_20,
                                                  geoid_bg_20, pop_overlap
      data/processed/acs_blockgroups.parquet      in-scope block groups

    Build the relationship first with src/acquire/ces_relationship.py, or
    make ces-relationship. The crosswalk is population weighted at the block
    group level. Writes data/processed/ces_dac_blockgroups.parquet and a manifest.
    """
    cfg = cfg or load_config()
    raw_dir = cfg.path("raw")
    interim = cfg.path("interim")
    processed = cfg.path("processed")

    ces_path = next((p for p in [raw_dir / "ces40.xlsx", raw_dir / "ces40.csv"] if p.exists()), None)
    if ces_path is None:
        raise FileNotFoundError("Drop CES 4.0 at data/raw/ces40.xlsx or data/raw/ces40.csv")
    rel_path = interim / "tract_rel_2010_2020.csv"
    if not rel_path.exists():
        raise FileNotFoundError(
            "Missing the population weighted relationship table at "
            "data/interim/tract_rel_2010_2020.csv. Build it with "
            "make ces-relationship, or python -m src.acquire.ces_relationship. "
            "It must carry columns geoid_tract_10, geoid_bg_20, pop_overlap."
        )

    ces_df = load_ces(ces_path)
    rel_df = pd.read_csv(
        rel_path, dtype={COL_TRACT10: str, COL_TRACT20: str, COL_BG: str}
    )
    block_groups = pd.read_parquet(processed / "acs_blockgroups.parquet")

    threshold = float(cfg["ces"]["dac_percentile_threshold"])
    assigned = build_blockgroup_crosswalk(ces_df, rel_df, threshold)
    report = coverage_report(assigned, block_groups["geoid_bg"].astype(str).tolist())

    ensure_dir(processed)
    assigned.to_parquet(processed / "ces_dac_blockgroups.parquet", index=False)

    manifest = {
        "source": "CalEnviroScreen 4.0, OEHHA",
        "tract_vintage_source": cfg["ces"]["tract_vintage_source"],
        "tract_vintage_target": cfg["ces"]["tract_vintage_target"],
        "weighting": cfg["ces"]["weighting"],
        "weight_basis": "2020_block_population_P1_001N",
        "crosswalk_resolution": "block group",
        "dac_percentile_threshold": threshold,
        "coverage_fraction": report.coverage_fraction,
        "total_in_scope_block_groups": report.total_in_scope,
        "covered_block_groups": report.covered,
        "missing_block_groups": list(report.missing_geoids),
        "pulled_at_utc": utc_now_iso(),
        "license": "Public, OEHHA CalEnviroScreen. Attribution requested.",
        "redistributable": True,
    }
    write_manifest(cfg.path("manifests") / "ces_dac_blockgroups.manifest.json", manifest)
    print(
        f"CES DAC coverage: {report.covered}/{report.total_in_scope} "
        f"({report.coverage_fraction:.1%}), missing {len(report.missing_geoids)}"
    )
    return report


if __name__ == "__main__":
    run()
