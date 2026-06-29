# Methods, Phase 4, optimizer and inference

Phase 4 turns the descriptive feasibility surface into a result. Three parts, the
budget constrained siting optimizer, the bootstrap confidence intervals, and the
robustness sweeps. The UI is not built here, that is a later phase.

## Part 1, siting optimizer

The optimizer selects where to add DCFC capacity, from the grid feasible
candidate sites only, under a per county port budget.

Decision. A binary variable per candidate and feasible tier. A site can be built
at a tier only if its joined grid cell can host that tier. A capacity_unknown site
has no feasible tier, so it is never selectable. The count excluded that way is
reported per county.

Linear access model. The integer program needs a linear objective, so the access
gain is the standard 2SFCA additive marginal. A new site at candidate c with s
ports adds, to each block group i in its catchment, an increment w_ic times R_c,
where R_c is s over the Gaussian weighted demand around c. This is additive across
sites, which ignores competition among the new sites, the usual and conservative
siting approximation. The optimizer runs on the descriptive point estimate
surface, Euclidean G2SFCA DCFC residential, at the 6 mile radius.

Two objectives, run and reported separately.

- Gap closing. Maximize the population weighted access gain in DAC block groups.
  Raising DAC area access closes the gap. The coefficient counts DAC benefit only,
  so the objective concentrates builds where DAC areas gain.
- Total gain. Maximize the equity weighted total access gain across the
  territory, with a heavier weight on DAC areas, default weight 2.

Constraints. A per county port budget, run at 5, 10, and 25 percent added to the
existing DCFC port count. One tier per site. Only feasible candidate tier pairs.
The program is a multiple choice knapsack, solved with CBC.

Objective contrast. Under the default equity weight of 2, the total gain
objective selects the same sites as gap closing, because DAC areas are also the
high population, low competition areas. There is little equity efficiency tradeoff
at that weight. A pure efficiency objective, equity weight 1, instead spreads
builds to high population non DAC areas and does not close the gap. The equity
weight is the policy lever.

## Part 2, bootstrap confidence intervals

Every headline number is a point estimate until it has an interval.

Spatial block bootstrap. Access in nearby block groups is autocorrelated, so an
iid resample understates the variance. The block is the census tract, the first
11 digits of the block group GEOID. Block groups in the same tract resample
together. Each resample draws tracts with replacement to the original tract
count, and takes all block groups in the drawn tracts. The statistic is computed
on each resample, 2000 of them, and the 95 percent percentile interval is the
confidence interval. The seed is fixed for reproducibility.

Intervals are put on the DAC access ratio per county, charger type, and method,
on the renter and multifamily quartile ratios, and on the optimizer gap closing
gain. The renter and multifamily ratios are reported too, not only the finding
under doubt. A ratio interval that excludes 1 is a real gap. An interval that
straddles 1 is within noise, which means no clear gap, not the opposite finding.

Orange has few DAC block groups, so its DAC interval is the relevant caution.

## Part 3, robustness sweeps

The findings are tested against reasonable alternative choices. The access DAC
ratio is swept over the catchment radius, 4, 6, and 10 miles, and the SFCA
method, G2SFCA, E2SFCA, and 3SFCA. The grid feasibility DAC contrast is swept over
the join threshold, 250, 500, and 1000 meters, the feasibility tier definitions,
a tighter and a looser MW set, and the diversity factor implied by those tiers.
For each county the question is whether the DAC disadvantage holds in sign and
rough size across the sweep, or flips. A finding that holds across methods and
thresholds is robust. One that flips is an artifact.

## What the paper can claim

The headline claim is exactly what survives Parts 2 and 3, no more. The DCFC DAC
access gap is real where its bootstrap interval excludes parity and its sign holds
across the sweep. Where the interval straddles parity, or the sign flips across
methods, the claim is no clear gap, stated plainly.
