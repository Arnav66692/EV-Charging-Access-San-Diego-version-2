# Methods, queueing supply adjustment, Phase 3

A charging port is not infinite throughput. Two vehicles cannot fast charge at
one port at once. Phase 2 treated supply as linear in ports, which overstates a
congested site. Phase 3 adds an M/M/c availability factor that scales a site's
supply down when it is congested. The raw port count is preserved alongside, it
is never overwritten.

## The availability factor

A site with c ports is an M/M/c queue. The availability factor is the
probability that an arriving vehicle finds a free port, which is one minus the
Erlang C probability of waiting. The effective supply is the raw port count
times this factor.

For a fixed arrival rate per port the utilization is constant in c, yet the
factor still rises with c. This is the pooling gain of a larger multi server
queue. Eight ports sharing demand serve more reliably per port than two ports
do. The classifier and the tests both rely on this property.

When a site is saturated, utilization at or above one, the factor is the served
fraction, one over utilization, which falls below one as it should.

## Inputs, pre specified

The inputs are config driven, in config.yaml under access.queueing.

- Mean service time. DCFC 40 minutes. L2 4 hours. A fast charge session and an
  L2 session differ by an order of magnitude, so they get separate service
  rates. The service rate is 60 over the mean service minutes, per hour.
- Arrival rate per port. DCFC 0.9 per hour. L2 0.15 per hour. These are set so a
  typical urban site runs at about 0.6 utilization, moderately loaded. Utilization
  is arrival per port over service rate, which is 0.9 over 1.5 for DCFC and 0.15
  over 0.25 for L2, both about 0.6.

## Modeled, not measured

The queueing inputs are modeled, not measured. There is no station level
utilization data in hand, so the arrival and service rates are stated
assumptions, not observations. This is a known limitation, named here rather
than hidden. The availability factor should be read as a structural adjustment
for congestion, not a calibrated load estimate. Station level utilization would
let a later phase calibrate these.

## Toggle

Queueing is a toggle, access.queueing.enabled. On for the primary spec. Off
recovers the Phase 2 linear supply exactly, since the factor is then 1.0 and the
effective capacity equals the raw port count. A test asserts that with the toggle
off the SFCA scores equal the Phase 2 linear scores exactly.
