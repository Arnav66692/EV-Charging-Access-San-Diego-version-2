# Grid fields, SCE ICA load capacity

This file records which field on the SCE ICA layer carries the load hosting value
used for feasibility, and why. The grid feasibility classification depends on
this field, so the semantics were confirmed from the layer, not assumed from the
name.

## Layer

- Dataset. ICA Circuit Segments, the Integration Capacity Analysis line section
  layer.
- Service. https://services5.arcgis.com/z6hI6KRjKHvhNO0r/arcgis/rest/services/ICA_Layer/FeatureServer/2
- Geometry. esriGeometryPolyline, line sections.
- Provider. Southern California Edison, DERiM open data site.

## Field used for load feasibility

The field used is **ica_overall_load**. It is read as load_capacity_mw, in MW.

This is the correct value for EV charging feasibility. It is the ICA load result,
the binding minimum. It reflects the most limiting power system criterion at the
most limiting hour. It is the conservative load hosting headroom on the section.

### Why this field, with evidence from the layer

The layer was inspected directly. The full field list for load and generation
results is below.

- ica_overall_load, String. The load result. This is the only load field.
- ica_overall_pv, Double. The generation result, PV.
- ica_overall_pv_op_flex, String. The generation result with operational
  flexibility.
- uniform_generation, Double. The uniform generation result.
- uniform_generation_op_flex, String. The uniform generation result with
  operational flexibility.
- most_limiting_factor, String. See the limiting factor section below.

Two facts confirm the choice.

1. There is exactly one load field. There is no ica_overall_load_op_flex and no
   uniform_load field. Operational flexibility, Op Flex, limits reverse power
   flow. Reverse power flow is a generation concern. So Op Flex variants exist
   only for generation, which the field list confirms. The single published load
   value is therefore the non Op Flex load value, which is what feasibility needs.

2. The prefix overall denotes the aggregate ICA result. In the SCE ICA
   methodology the published value is the minimum across all evaluated power
   system criteria and across the hourly profile. That minimum is the binding
   value. ica_overall_load is that binding load value.

### Verbatim text captured from the portal

The ArcGIS REST layer does not expose a per field description. The desc property
is null for every field. The definitions below are the verbatim strings the
portal does publish.

- Dataset disclaimer, verbatim. "While Southern California Edison makes every
  effort to ensure the accuracy of DRPEP, the data provided is for information
  purposes only. Southern California Edison makes no guarantee, expressly or
  implied, for the outcome of an interconnection request."
- Section note, verbatim, sampled from a constrained circuit. "This is a
  potentially constrained circuit. Load was aggregated for this circuit due to
  failure of the 15/15 rule. Please see user guide for more details."
- Refresh note, verbatim from the dataset description. "ICA monthly refresh for
  June 2026 is completed."

The full field definitions live in the SCE ICA user guide referenced by the
section note. The user guide is not exposed as a fetchable field description on
the service. The semantic confirmation here rests on the field structure, the
published values, and the SCE ICA methodology under the CPUC Distribution
Resources Plan proceeding.

## Limiting factor, a correction

The field most_limiting_factor was first read as a generic limitation category.
Inspection shows it is generation oriented, not a load limitation.

A grouped count over the whole layer returns these values.

| most_limiting_factor | count |
| --- | --- |
| Generation - Steady State Voltage | 317076 |
| Generation - Thermal | 128912 |
| Generation - Protection | 32825 |
| Generation - Voltage Variation | 26342 |
| NA | 19367 |

Every non NA value is prefixed Generation. There are zero Load prefixed values.
So this field reports the factor that limits generation hosting, not load
hosting. It is captured as **generation_limiting_factor** and is not presented as
a load constraint. The load side limiting factor is not published on this layer.

This was corrected in config.yaml and src/acquire/sce_derim.py. The standardized
column is generation_limiting_factor. The join carries it under that honest name.

## Fields not used, and why

- ica_overall_pv, uniform_generation, and the Op Flex variants. These are
  generation results. The study constraint is added load, not added generation.
- Circuit Load Profile, on the separate ICA_Tables service. That is the existing
  hourly load shape, not the hosting capacity. It is not the feasibility value.

## Result

The load field is confirmed. No change was needed to the load field itself.
ica_overall_load is correct. The limiting factor field was renamed to reflect its
true generation semantics.
