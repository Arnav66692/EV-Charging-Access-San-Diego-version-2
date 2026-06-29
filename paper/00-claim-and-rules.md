# Core claim, framing rules, open flags, frozen numbers

This folder holds the paper text only. The analysis code, data pipeline, web map,
result manifests, and data files stay where they are. The paper draws on the
frozen results, it does not own them.

## Locked core claim (the paper argues exactly this, no more)

The disadvantaged-community DC fast-charging gap is an imbalance between nearby
supply and the higher competing demand of dense disadvantaged areas. A
competition-aware accessibility model from the 2SFCA family reveals this gap
where a proximity or station-count model misses it. The gap is real in San Diego
and Los Angeles, where supply does not scale with that demand, and reversed in
Orange County, where it does, so the gap is geographic and tracks the
supply-to-demand balance, not the disadvantaged-community label. Grid
distribution hosting-capacity constraints then bound how much budget-constrained
equity-weighted siting can close the gap, severely in LA, partly because much of
LA's disadvantaged area sits in LADWP territory and cannot be assessed at all.

## Framing rules

1. The mechanism is the contribution, the ratios are its evidence. Not a
   two-county measurement study.
2. Associational language only, never causal. The diagnostic reproduces the sign
   of the ratios.
3. Four caveats stated up front in the intro scope paragraph. Modeled demand and
   queueing not measured. Screening-grade ICA not an interconnection guarantee.
   Descriptive not causal. SDG&E data not redistributable, so San Diego grid
   results are derived outputs.
4. Orange is the keystone, named, not a hedge. The renter and multifamily
   falsification is a contribution.
5. DAC count is not the mechanism. San Diego has the fewest DACs and still shows
   a gap.
6. The per-capita diagnostic is explanatory only, never the headline metric.
7. No pre-registration claim. This paper is not pre-registered.

## Open flags (wording and figure-sourcing guards from the outline review)

1. Mechanism prose says "accounts for" or "reproduces," never "causes" or
   "drives."
2. The LA optimizer cap splits into within-SCE scarcity (evidence) first and
   unassessable LADWP territory (data limitation) second. The LADWP portion is
   not the grid being physically full.
3. The static access-map figure renders derived outputs only, no SDG&E load
   value, same firewall as the public map.
4. The per-capita diagnostic panel is labeled a proxy consistent with but not
   identical to the 2SFCA surface. It understates Orange and slightly overstates
   LA.

## Frozen numbers

- DCFC DAC/non-DAC 2SFCA access ratio, spatial block bootstrap 2000, block is
  census tract, 95 percent CI. San Diego 0.725 [0.599, 0.889], local, vanishes
  at 10 mi. LA 0.807 [0.767, 0.834], robust across method and radius. Orange
  1.147 [1.093, 1.201], DAC better served.
- Mechanism diagnostic. DCFC ports per 1,000 competing residents in catchment
  reproduces the sign of all three ratios (SD 0.74, LA 0.74, Orange near parity).
  Raw proximity favors DAC areas in all three counties.
- Robustness. The gap holds across G2SFCA, E2SFCA, 3SFCA in all counties. LA
  across radii. SD at 4 to 6 mi, not 10. The grid-feasibility gap survives
  threshold, diversity, and tier sweeps.
- Falsification. Renter and multifamily groups are not disadvantaged in any
  county, CI excludes parity. L2 is noisy, no L2 claim.
- Optimizer. Gap-closing siting moves San Diego 0.728 to 1.504 at 10 percent
  budget, confirmed under a nonlinear recompute. LA capped near 0.95 even at 25
  percent, bounded by within-SCE scarcity and 8,855 unassessable LADWP DAC
  candidates. The equity weight is the policy lever.
