# Grid-Constrained, Equity-Aware DC Fast-Charging Accessibility Across Two California Utility Territories

Target venue: IEEE Access. Fallback: IEEE ITEC.

Draft sections only. The abstract and introduction are drafted here. Later sections
are drafted in subsequent passes, see 01-outline.md.

## Abstract

Direct-current fast-charging equity is usually assessed by proximity or by station
counts per capita. Both miss how nearby supply is shared among competing demand. We
study disadvantaged-community fast-charging access across two California utility
territories, San Diego under SDG&E and Orange and Los Angeles under SCE, with a
competition-aware accessibility model from the two-step floating catchment area
family. The gap is an imbalance between nearby supply and the higher competing
demand of dense disadvantaged areas, so it is geographic, not categorical. Access
is lower in San Diego, ratio 0.725, 95 percent CI 0.599 to 0.889, though local and
vanishing at a ten-mile catchment, and in Los Angeles, ratio 0.807, CI 0.767 to
0.834, robust across method and radius. It reverses in Orange County, ratio 1.147,
CI 1.093 to 1.201, where supply scales with demand. A per-capita supply diagnostic
reproduces the sign of all three ratios, while raw proximity favors disadvantaged
areas everywhere. Renter and multifamily groups are not disadvantaged in any
county, with intervals excluding parity, which shows the deficit is specific to the
disadvantaged-community supply-demand geography, not a generic equity artifact.
Coupled to multi-utility distribution-grid hosting capacity, equity-weighted siting
closes the San Diego gap substantially but only partly the Los Angeles gap, bounded
by within-utility scarcity and by disadvantaged areas in unassessable LADWP
territory. San Diego grid results are reported as derived outputs, because the
SDG&E hosting-capacity data is not redistributable. The analysis is descriptive
rather than causal, and the feasibility is screening-level. The heterogeneity and
the grid-bounded siting give a more precise basis for equity-aware charger
deployment than proximity or station count.

## I. Introduction

Electric vehicle adoption depends on access to public direct-current fast charging,
and that access is not evenly distributed. Policy attention has centered on
disadvantaged communities, the areas flagged by screening tools such as
CalEnviroScreen for combined pollution and socioeconomic burden. Most equity
assessments measure access by proximity, the distance to the nearest charger, or by
station counts per capita within a region. These framings share a blind spot. They
count nearby supply but not the demand that competes for it. A charger beside a
dense neighborhood is shared by more people than the same charger beside a sparse
one, so two areas with identical proximity can have very different real access.
Dense disadvantaged areas place more competing demand on each nearby charger, which
is where this matters most. A competition-aware accessibility model is needed to
see the gap that proximity and counts miss. That model, and the supply-to-demand
balance it exposes, is the through-line of this paper.

The gap we find is geographic, not categorical, and the distinction is central.
Categorical would mean the disadvantaged-community label itself marks lower access,
a uniform deficit attached to the category wherever it appears. Geographic means
the gap depends on where disadvantaged communities sit relative to supply, and on
whether the supply near them scales with their higher demand. Under the categorical
reading every disadvantaged area would be underserved. Under the geographic reading
some are and some are not, and which case holds tracks the local supply-to-demand
balance. Our results match the geographic reading. Disadvantaged communities are
charger-adjacent and dense in all three counties, yet their measured access is
lower in two and higher in one. Access lines up with the local supply-to-demand
balance, not with the label.

Two gaps in the literature follow. First, charging-equity studies rarely use a
competition-aware metric, so they cannot separate the categorical reading from the
geographic one, and a uniform deficit they report would be falsified by a single
counterexample. Second, accessibility and grid feasibility are studied apart.
Accessibility work seldom asks whether the distribution grid can host new chargers
where equity wants them, and grid-aware siting work seldom starts from a
competition-aware equity diagnosis. This paper joins the two. It measures access
with a competition-aware model, accounts for the result with a supply-to-demand
diagnostic, and couples it to multi-utility hosting-capacity feasibility to ask how
much equitable siting the grid actually permits.

This paper makes four contributions. First, a competition-aware accessibility
analysis of DC fast-charging equity, not proximity or station count, across two
utility territories. Second, a multi-utility distribution-grid hosting-capacity
feasibility fusion, combining the SCE DERiM and the SDG&E-derived ICA layers,
coupled to equity-weighted siting. Third, an honest account of county heterogeneity
with a mechanism, the supply-to-competing-demand balance, including a named
counterexample in Orange County, where disadvantaged areas are better served.
Fourth, a replicated and stress-tested falsification of the renter-disadvantage
assumption, showing that renter and multifamily groups are not disadvantaged on
fast-charging access in any county, with intervals excluding parity.

We bound the claims at the outset. Four scope decisions shape what the evidence can
support. We model demand and queueing because station-level utilization is not
publicly available, so a modeled surface is the best evidence the data permit. We
report hosting capacity from a most-limiting-hour interconnection capacity
analysis, which shows where capacity is likely available, and we treat it as a
screening signal rather than an interconnection guarantee. We keep the design
descriptive and report associations between disadvantaged-community status and
access, and we do not claim that the status causes the gap. We report San Diego
grid results as derived outputs under the SDG&E data terms, because the underlying
layer is not redistributable. Within these bounds, the findings follow.

The paper proceeds as follows. Section II positions the work against the
charging-equity, accessibility, and grid-constrained siting literatures. Section
III describes the study area and data. Section IV presents the methods, with
accessibility and grid feasibility in separate subsections, and states that the
access metric uses no grid data. Section V reports the results, the headline access
gap, the proximity-versus-competition mechanism, the robustness and falsification,
the grid feasibility gap, and the siting outcome. Section VI discusses the policy
reading. Section VII states the limitations in full. Section VIII concludes.

## IV. Methods

Section IV-A measures accessibility. Section IV-C measures grid feasibility. The two
are kept separate on purpose, and the accessibility metric uses no grid data. The
following subsections give enough detail to rebuild the pipeline. Parameter values
are the configured values used for the reported results.

### IV-A. Accessibility, competition-aware

We measure access with the two-step floating catchment area family. The spatial unit
is the census block group. Demand sits at the population-weighted centroid of each
block group, from the Census 2020 centers of population. Distances are computed in
California Albers, EPSG 3310, an equal-area meters projection, with geometries stored
in EPSG 4326. Supply is the count of DC fast-charging ports at each station, from the
Alternative Fuels Data Center. Demand is residential population, from the American
Community Survey five-year release for 2019 to 2023, table B01003. Residential
population is the primary DC fast-charging demand, and workplace jobs from LODES are a
pre-specified demand sensitivity.

Supply carries a queueing availability factor. A port is not infinite throughput, so a
congested site counts for less. We scale each station's ports by an M/M/c availability
factor, with an arrival rate of 0.9 vehicles per port per hour and a mean service time
of 40 minutes for DC fast charging, which holds a typical urban site near 0.6
utilization. This factor is modeled, not measured, because station-level utilization is
not publicly available. Setting it off recovers the linear supply exactly.

The Gaussian two-step floating catchment area, G2SFCA, is the headline method, in the
Dai 2010 form. The first step computes a supply-to-demand ratio at each charger. For
charger j, the ratio is the ports at j divided by the sum of population at every block
group within the catchment, each weighted by a Gaussian decay that is one at the
charger and zero at the catchment edge. This denominator is the competition term. It
counts the demand that competes for charger j, so a charger surrounded by dense
population earns a lower ratio than the same charger in a sparse area. The second step
computes access at each block group. For block group i, access is the sum, over
chargers within the catchment, of the charger ratio, each weighted by the same Gaussian
decay. Access is therefore supply per competing capita, reachable and
distance-discounted, not raw proximity.

Travel cost is straight-line distance. The reported surface uses straight-line distance
at a six-mile catchment for DC fast charging. A drive-time backend over OSRM, with a
fifteen-minute threshold, is implemented as a travel-cost alternative. We report
robustness across method and radius. The enhanced form, E2SFCA, in the Luo and Qi 2009
form, replaces the smooth decay with three zones broken at one third and two thirds of
the catchment, weighted 1.0, 0.68, and 0.22. The three-step form, 3SFCA, adds a
selection weight that apportions demand across competing chargers. The headline
catchment radius is six miles. We sweep four, six, and ten miles.

The access metric uses no grid data. Its inputs are charger ports as supply, population
as demand, and distance as travel cost, with the queueing factor on supply using
charging-session rates only. No hosting capacity, no feasibility tier, and no
distribution-grid quantity of any kind enters the two-step computation. A reader can
verify this line by line. The grid does not touch the accessibility metric.

### IV-B. Per-capita diagnostic

To account for the access ratios we use a coarse diagnostic, DC fast-charging ports per
one thousand competing residents in catchment. For each block group we sum the ports at
every station within a six-mile straight-line cutoff, sum the residential population
within the same cutoff, and divide. This is an explanatory device, not the access
metric. It uses a hard distance cutoff, with no Gaussian decay, no two-step
normalization, and no queueing factor, so it is coarser than the two-step access of
IV-A. It tracks the sign and the approximate magnitude of the 2SFCA ratios but is not
identical to them. The headline access numbers are the 2SFCA values of IV-A. The
diagnostic accounts for those values, it does not replace them. We use it only to show
which side of the supply-to-demand balance each county falls on.

### IV-C. Grid feasibility fusion

The grid enters the analysis only in this subsection and in the siting optimizer of
IV-D. It never enters the accessibility metric of IV-A.

Feasibility comes from interconnection capacity analysis, the utility hosting-capacity
layer. We read the most-limiting-hour load hosting value in megawatts at each grid
section, the load capacity available in the worst hour. For Southern California Edison
this is the overall ICA load field of the DERiM layer. For San Diego Gas and Electric
it is the uniform-load ICA field of the load-capacity layer. We join each candidate
charging site to the nearest grid section within 500 meters, computed in EPSG 3310, and
beyond that distance a candidate is left unjoined rather than forced onto a far section.

We classify each joined candidate into a feasibility tier by the load headroom a build
of that size would require. Required headroom is ports times kilowatts per port times a
diversity factor, divided by one thousand. The diversity factor is 1.0, full
simultaneity, the conservative screening assumption. The tiers are small, two
150-kilowatt ports, 0.3 megawatts, medium, four 150-kilowatt ports, 0.6 megawatts, and
large, eight 350-kilowatt ports, 2.8 megawatts. A candidate is feasible at a tier if
its joined section's load capacity meets that tier's required headroom.

We fuse two utility sources. Southern California Edison publishes its layer through the
DERiM portal, redistributable, used for Orange and Los Angeles. San Diego Gas and
Electric publishes its layer under terms that are not redistributable, used for San
Diego. We therefore report all San Diego grid results as derived outputs, the
feasibility tiers, never the underlying capacity values.

Two coverage matters are explicit. Where a candidate has no readable capacity within
the join distance we mark it capacity_unknown and exclude it from feasibility, rather
than assume it feasible. A large share of Los Angeles disadvantaged area sits in Los
Angeles Department of Water and Power territory, which the DERiM layer does not cover,
so those candidates are capacity_unknown by data coverage, not by grid scarcity. We
keep this coverage gap distinct from genuine capacity scarcity throughout.

### IV-D. Siting optimization

We site new ports with a budget-constrained integer program over the grid-feasible
candidate set. Each candidate may be built at one feasibility tier or not at all, a
multiple-choice knapsack. The budget is a per-county cap on new ports, set as a
fraction of the existing DC fast-charging port count, swept at 5, 10, and 25 percent,
with 10 percent as the headline build. capacity_unknown candidates are not selectable,
so the optimizer can build only where the grid is assessed and feasible.

We solve two objectives, run and reported separately. The total-gain objective
maximizes the access gain summed over all block groups. The gap-closing objective
weights gain in disadvantaged areas more heavily, through an equity weight of 2.0 on
disadvantaged-community demand. The equity weight is the policy lever. At a weight of
2.0 the gap-closing and total-gain selections coincide. At a pure-efficiency weight of
1.0 the build spreads to non-disadvantaged areas and does not close the gap.

The objective evaluates access gain as the 2SFCA marginal of adding a candidate, the
additive change each new site brings to the two-step access on the straight-line
G2SFCA residential surface. A linear marginal can overstate gain when access saturates.
We confirm the selected build against a nonlinear recompute, rerunning the full
two-step with the chosen sites added to supply rather than summing marginals. The two
agree closely, so we report the optimizer gains as computed.

### IV-E. Inference

We quantify uncertainty with a spatial block bootstrap. The block is the census tract,
so block groups in the same tract resample together, which respects spatial
autocorrelation. We draw two thousand resamples, with seed 12345, and report 95 percent
percentile confidence intervals. On each resample we recompute the
disadvantaged-community access ratio, the population-weighted median access in
disadvantaged areas divided by the same in non-disadvantaged areas. A block group is
disadvantaged if its CalEnviroScreen 4.0 percentile is at or above 75, crosswalked from
2010 to 2020 tracts by population.

We test robustness with the method and radius sweeps of IV-A, recomputing the ratio for
G2SFCA, E2SFCA, and 3SFCA, and for the four, six, and ten-mile catchments. We also
sweep the grid-feasibility knobs, the join threshold at 250, 500, and 1000 meters, the
diversity factor at 1.0 and 0.6, and three tier sets.

We falsify a competing explanation, that the deficit is a generic disadvantage of
renters or apartment dwellers rather than the disadvantaged-community supply-demand
geography. On the same access surface we compute access ratios for the top versus
bottom quartile of renter share, from ACS tenure table B25003, and of
multifamily-housing share, from ACS units-in-structure table B25024, each with
bootstrap intervals. If those groups were disadvantaged on access, their ratios would
fall below parity. We report whether they do.
