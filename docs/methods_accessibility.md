# Methods, accessibility engine, Phase 2

This phase computes EV charging accessibility per block group across the three
in-scope counties. It produces accessibility surfaces and the descriptive
disadvantaged community access ratio. It does not model the queueing supply, the
grid feasibility join, or the siting optimizer. Those are later phases.

## Architecture

The travel cost layer is separate from the accessibility math. The math is a
pure engine that consumes an origin destination structure. It needs no OSRM and
no Docker, so it is fully unit tested on a synthetic OD matrix with a hand
computed answer.

An OD cost provider returns a sparse within-catchment set of origin, supply, and
cost. There are two backends. The euclidean backend is straight line distance in
EPSG:3310. The osrm backend is drive time and drive distance from the OSRM table
service on the Phase 1 instance. The osrm backend is injectable, so it mocks in
tests and the build never waits on a live OSRM.

## Two run modes

The v1-compat gate uses the euclidean backend, the v1 radii, geometric
centroids, G2SFCA, and residential demand. It reproduces v1's San Diego DCFC
result. It needs no Docker.

The primary mode uses the osrm backend, drive time, type differentiated
thresholds, population weighted centroids, all three SFCA methods, and the
residential plus LODES demand sensitivity. The live drive time run waits on the
user's Docker.

## Travel cost and the water artifact

Network cost removes the v1 Euclidean across water artifact for free. Routing
uses real roads and real bridges. A straight line can cross San Diego Bay where
no road does, which overstates access. Drive time cannot. So no manual bay
crossing exclusion is needed once cost is network based. This is a direct benefit
of the switch from straight line distance to drive time.

## Centroids

Primary mode uses population weighted centroids from the 2020 block group
centers of population file. That places the origin where people are, not at the
geometric middle of the polygon. Geometric centroids are kept only for the
v1-compat gate, which reproduces v1, which used geometric centroids.

## Time thresholds

Thresholds differ by charger type and are pre-specified. The default is 15
minutes for DCFC and 7 minutes for L2. Fast charging serves longer trips, so it
gets a wider time budget. L2 charging is local, so it gets a tighter one. The
threshold sweep is Phase 4 and is not run here.

## KD-tree prefilter

The prefilter must never drop a reachable pair. Network distance is always at
least Euclidean distance. So a Euclidean buffer set to the threshold converted at
a generous upper bound speed of 70 mph is a safe superset. Only prefiltered pairs
are routed with OSRM. Survivors inside the true threshold are kept. A test
confirms the prefilter produces no false negatives against a brute force check.

## SFCA methods

All three methods share one two step gravity core. They differ only in the pair
weight m_ij.

  step one, supply to demand ratio   R_j = S_j / sum_i m_ij D_i
  step two, accessibility            A_i = sum_j m_ij R_j

G2SFCA, Dai 2010. The decay is the normalized Gaussian. For a cost d within the
threshold d0 the weight is w = (exp(-0.5 (d/d0)^2) - exp(-0.5)) / (1 - exp(-0.5)),
and 0 beyond d0. Here m_ij is w_ij.

E2SFCA, Luo and Qi 2009. The decay is discrete distance zones. Each zone covers a
band of d over d0 and carries a fixed Gaussian derived weight. The zones and
weights are in config. Here m_ij is the zone weight.

3SFCA, Wan, Steinbach, and Wang 2012. It adds the Huff style selection weight
G_ij = S_j w_ij / sum_k S_k w_ik, summed over supplies k reachable from origin i.
This allocates each demand across the competing reachable supplies, which
corrects the demand overestimation of the two step methods. Here m_ij is
G_ij w_ij.

## Demand and supply

Residential population is the L2 demand and the primary DCFC demand. It comes
from the Phase 1 ACS pull. LODES workplace jobs is the pre-specified DCFC demand
sensitivity. It comes from the LEHD LODES8 Workplace Area Characteristics for
California, at block level, with no API key, summed to the block group. The
reasoning is that fast charging often serves trips anchored at work and other
non home destinations, so a workplace weighted denominator is a sensible alternate
for DCFC.

Supply is AFDC stations, split by charger type. The capacity is the port count
for that type. DCFC ports and L2 ports are separate supplies with separate
thresholds.

## Descriptive DAC access ratio

The estimand is the population weighted median access in DAC block groups over
the population weighted median access in non DAC block groups. It is reported per
territory, charger type, and method. This is the v1 estimand. A ratio below 1
means DAC block groups have lower typical access. This phase is descriptive only.
The bootstrap and the robustness sweeps are Phase 4.

## Reproducibility

The surfaces move whenever the inputs move. So every access row records the AFDC
snapshot file and sha256 it was computed from, the run mode, and a config hash.
FIPS identifiers are strings. Costs and joins are in EPSG:3310.

## The v1-compat gate

The gate runs v1-compat mode for San Diego and writes a documented result. There
are two paths.

The exact reproduction path runs when the user provides v1's frozen AFDC snapshot
and v1's recorded San Diego DCFC ratio. The gate recomputes the ratio from that
station set and asserts it matches within a documented tolerance.

The qualitative pattern path runs when v1's snapshot is not available. The station
set then differs, so exact reproduction is impossible. The gate asserts the
qualitative pattern instead. The DCFC ratio is below 1, and there is a proximity
reversal versus a naive nearest distance measure. Nearest distance flatters the
DAC areas. SFCA, which accounts for supply and competition, reveals lower access.
The gate output records which path ran.
