# Methods, grid feasibility join, Phase 3

This join fuses the frozen SCE ICA load capacity layer to candidate sites and
classifies each candidate by the fast charging build the local grid can host. It
is SCE only, since the SDG&E load capacity layer is not in hand. It is the first
cross county grid result the single territory v1 work could not produce.

## Site size tiers

Each tier needs a load headroom in MW. The requirement is ports times kW per
port times a diversity factor, divided by 1000. Tiers are config driven, in
config.yaml under grid_feasibility.

- small, 2 ports at 150 kW, 0.3 MW.
- medium, 4 ports at 150 kW, 0.6 MW.
- large, 8 ports at 350 kW, 2.8 MW.

The diversity factor is 1.0, full simultaneity. Every port is assumed at its
rated peak at once. This is the conservative screening choice, it does not give a
site credit for load diversity it may not have. A later phase could relax it with
a stated diversity factor below one, which would lower the MW requirement and
raise feasibility shares.

Diversity factor note. The 1.0 full simultaneity assumption is deliberately
conservative. Real charging sites rarely see every port at rated peak at the same
instant, so operators apply a diversity factor below one when sizing service. A
factor of, say, 0.6 would cut each tier requirement to 0.18, 0.36, and 1.68 MW
and would raise the feasible shares. The tier requirements are not changed here.
A diversity sensitivity, sweeping the factor and reporting how feasibility shares
move, is deferred to Phase 4. For now the reported shares are a conservative
lower bound on feasibility.

## Classification

Each candidate is already joined to its nearest SCE line section within the snap
threshold. The section's ica_overall_load is its most limiting hour load
headroom in MW. A candidate is feasible at a tier when the section headroom is at
least the tier requirement. The output is a per candidate feasibility vector,
feasible_small, feasible_medium, feasible_large, plus the raw section MW.

Tier requirements are monotone, small below medium below large, so any candidate
feasible at large is feasible at medium and small. A test asserts this.

## Honest redaction and coverage handling

SCE applies a 15/15 redaction, so some sections publish no capacity. A candidate
is flagged capacity_unknown, never marked feasible or infeasible, in two cases.

- capacity_redacted. The candidate joined to a section whose ica_overall_load is
  null, the 15/15 redaction.
- no_section_within_threshold. The candidate had no SCE section within the snap
  threshold, so there is no capacity to read.

The grid_status column records which case applies, so the unknown bucket is not
opaque. Feasibility shares are reported among capacity known candidates, and the
capacity_unknown share is reported separately, since an unknown is not an
infeasible.

## Screening level only

This is a screening result, not an interconnection guarantee. It is the ICA most
limiting hour headroom. Upgrades may still be required. The verbatim SCE caveat,
also recorded in docs/grid_fields.md, is.

"While Southern California Edison makes every effort to ensure the accuracy of
DRPEP, the data provided is for information purposes only. Southern California
Edison makes no guarantee, expressly or implied, for the outcome of an
interconnection request."

## Coverage gap

San Diego is not included. The SDG&E load capacity layer is gated and not in
hand, so SDG&E territory candidates cannot be classified. This is a stated
coverage gap, the cross county result covers Orange and Los Angeles only.

## Coverage diagnostic, Phase 3.5

The first feasibility run had a high capacity_unknown share, about 50 percent.
A diagnostic split that into two distinct causes.

The Orange County share was a candidate acquisition artifact. The OSM Overpass
query matched the county by name, and Orange County is not unique in the United
States, so the candidate set was polluted with parking lots from other states.
About 51 percent of Orange candidates fell outside California. The query now
scopes the county within California first, see src/acquire/osm_osrm.py. After the
fix Orange capacity_unknown fell from 58.5 percent to 14.5 percent, and 87
percent of Orange candidates have a section within 500 m.

The Los Angeles share is a real coverage hole, not a threshold artifact. The
LADWP municipal utility serves the City of Los Angeles and other parts of LA
County, and SCE does not. The SCE ICA layer therefore has no sections there. Of
the LA candidates with no section within 500 m, about 69 percent have zero SCE
sections within 2 km, a clean coverage boundary, not a gradual threshold falloff.
Raising the threshold does not fix it, 14.6 percent still have no section even at
5 km. The 500 m threshold is kept, since it is a defensible urban service drop
distance and the gap is honest, not a threshold to be inflated away. LA DAC areas
sit disproportionately in LADWP territory, so their capacity_unknown is higher,
52.7 percent versus 38.2 percent for non DAC. The LA DAC versus non DAC
feasibility contrast, computed on capacity known candidates only, is unchanged by
the Orange fix, so it is a real finding for the SCE served portion of LA, with
the LADWP coverage caveat stated.
