# Section outline, IEEE Access

**Abstract.** Method, heterogeneity with Orange named, supply-versus-competing-demand
mechanism stated associationally, grid-bounded siting with the LA caveat, and the
four caveats compressed. Carries the locked core claim.

**Index Terms.** Electric vehicle charging, accessibility, spatial equity, two-step
floating catchment area, distribution grid hosting capacity, facility siting.

**I. Introduction.** The DCFC equity problem and why proximity or station-count
framing is insufficient. The geographic-not-categorical distinction with a clear
referent. The gap this paper fills. Four contributions. One scope-and-ceiling
paragraph with the four caveats. Roadmap. Carries the core claim and the up-front
caveats.

**II. Related Work.** Three categories with one-line differentiators. National
charging-equity studies, the SFCA/2SFCA accessibility literature, and EV siting
with grid constraints. Carries positioning.

**III. Study Area and Data.** Two utility territories, three counties, sources
(AFDC, ACS, CalEnviroScreen DAC flag, OSM, SCE DERiM, SDG&E ICA as input only).
DAC definition. SDG&E not redistributable, San Diego grid results derived.
Carries provenance and the firewall caveat.

**IV. Methods.** The accessibility-versus-feasibility split is enforced here.
- IV-A Accessibility, competition-aware. The 2SFCA family, G2SFCA headline plus
  E2SFCA and 3SFCA, catchment radii, residential demand, the competition term.
  Explicit sentence that the access metric uses no grid data.
- IV-B Per-capita diagnostic. DCFC ports per 1,000 competing residents, labeled a
  diagnostic for the ratios, not the headline metric, not grid-aware.
- IV-C Grid feasibility fusion. ICA hosting capacity to feasibility tiers across
  SCE DERiM and the SDG&E-derived layer, capacity_unknown handling, LADWP
  unassessable. Explicit sentence that the grid enters only here and in the
  optimizer.
- IV-D Siting optimization. Equity-weighted budget-constrained integer program,
  gap-closing and total-gain objectives, equity weight as the policy lever.
- IV-E Inference. Spatial block bootstrap (block is tract, 2000), CIs, method and
  radius sweeps, falsification design (renter Q4/Q1, multifamily Q4/Q1).

**V. Results.**
- V-A Headline access gap and heterogeneity. Three ratios with CIs. SD local
  (vanishes at 10 mi). LA strongest. Orange keystone reversal. Table 1.
- V-B Mechanism, proximity versus competition. Proximity favors DAC everywhere,
  per-capita reproduces the signs. Orange explained. Keystone figure.
- V-C Robustness and falsification. Method and radius sweeps. Renter and
  multifamily not disadvantaged. No L2 claim. Tables 2 and 3.
- V-D Grid feasibility gap. DAC feasible-tier share by county. SD and LA
  negative, Orange positive. The within-SCE LA evidence. Feasibility figure.
- V-E Siting under the grid constraint. Optimizer contrast. SD closes, LA caps.
  Cap attributed to within-SCE scarcity first, unassessable LADWP second.
  Optimizer figure.

**VI. Discussion.** Policy reading, equity weight as the lever, supply-must-scale
interpretation in associational language. The two LA pieces kept distinct,
evidence versus data limitation.

**VII. Limitations.** The four caps in full plus the diagnostic-is-a-proxy and the
LADWP coverage as a data limitation, not a physical grid limit.

**VIII. Conclusion.** Restates the locked claim and the policy implication. No new
claims.

**Data and Code Availability.** The public interactive map referenced as a
resource, derived outputs only, firewall noted. Not a figure.
