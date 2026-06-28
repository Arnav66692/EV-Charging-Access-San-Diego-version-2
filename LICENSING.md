# Licensing

This project fuses several sources. Licensing is asymmetric. Some sources are
redistributable and may live in committed processed outputs. One source is input
only and must never be redistributed. This file records the terms per source.

The verbatim terms below are copied from each source portal where they were
available at capture time. Where a portal shows its terms only behind an account
or a click through, that is noted, and the maintainer should paste the exact
text before any public release.

## Summary table

| Source | Redistributable | In committed outputs |
| --- | --- | --- |
| AFDC stations, NREL | Yes | Yes |
| ACS, U.S. Census | Yes | Yes |
| CalEnviroScreen 4.0, OEHHA | Yes | Yes |
| OpenStreetMap | Yes | Yes |
| SCE DERiM ICA layer | Yes | Yes |
| SDG&E ICA layer | No | No, gitignored |

---

## AFDC stations

- Name. Alternative Fuel Data Center, Alternative Fueling Station Locator.
- Provider. National Renewable Energy Laboratory, U.S. Department of Energy.
- URL. https://developer.nrel.gov/docs/transportation/alt-fuel-stations-v1/
- Access. NREL Developer Network API. Requires a free API key.
- Terms, verbatim from the NREL API terms. "This product uses the NREL API but
  is not endorsed or certified by NREL." NREL data produced by the U.S.
  Government is in the public domain.
- Redistributable. Yes.
- Attribution string. "This product uses the NREL API but is not endorsed or
  certified by NREL. Station data from the U.S. DOE Alternative Fuel Data
  Center."

## ACS block group demographics

- Name. American Community Survey, 5 year, block group tables. Vintage 2023,
  covering 2019 to 2023.
- Provider. U.S. Census Bureau.
- URL. https://www.census.gov/data/developers/data-sets/acs-5year.html
- Access. Census Data API. A free API key is required as of capture time. A
  request without a key returns a missing key page.
- Terms. Works of the U.S. Government are in the public domain. The Census API
  terms of service ask that you not imply Census Bureau endorsement and that you
  cite the source.
- Redistributable. Yes.
- Attribution string. "Source, U.S. Census Bureau, American Community Survey 5
  year, 2019 to 2023."

## CalEnviroScreen 4.0

- Name. CalEnviroScreen 4.0, disadvantaged community percentile.
- Provider. California Office of Environmental Health Hazard Assessment, OEHHA,
  and CalEPA.
- URL. https://oehha.ca.gov/calenviroscreen/report/calenviroscreen-40
- Terms. CalEnviroScreen is published by a California state agency for public
  use. Confirm the OEHHA conditions of use on the page before public release and
  paste the exact text here.
- Redistributable. Yes.
- Attribution string. "CalEnviroScreen 4.0, OEHHA and CalEPA."
- Note. CES 4.0 is published on 2010 census tracts. This project crosswalks it to
  2020 tracts with the Census 2010 to 2020 tract relationship file, population
  weighted. See README.

## OpenStreetMap candidate sites

- Name. OpenStreetMap features, parking, civic, retail, and park and ride.
- Provider. OpenStreetMap contributors.
- URL. https://www.openstreetmap.org/copyright
- Terms, verbatim. "OpenStreetMap is open data, licensed under the Open Data
  Commons Open Database License, ODbL, by the OpenStreetMap Foundation, OSMF."
  And. "You are free to copy, distribute, transmit and adapt our data, as long
  as you credit OpenStreetMap and its contributors."
- Redistributable. Yes, under ODbL 1.0 with attribution and share alike.
- Attribution string. "© OpenStreetMap contributors, ODbL."

## SCE DERiM ICA layer

- Name. ICA Circuit Segments, the Integration Capacity Analysis load capacity
  line section layer.
- Provider. Southern California Edison, SCE C-GIS Project, DERiM open data site.
- URL. https://drpep-sce2.opendata.arcgis.com/datasets/SCE2::ica-circuit-segments
- Service. https://services5.arcgis.com/z6hI6KRjKHvhNO0r/arcgis/rest/services/ICA_Layer/FeatureServer/2
- Terms, verbatim from the dataset license field. "While Southern California
  Edison makes every effort to ensure the accuracy of DRPEP, the data provided is
  for information purposes only. Southern California Edison makes no guarantee,
  expressly or implied, for the outcome of an interconnection request."
- Redistributable. Yes. This is published open data.
- Attribution string. "Grid hosting capacity from Southern California Edison
  DERiM, ICA Circuit Segments."

## SDG&E ICA layer

- Name. SDG&E Integration Capacity Analysis load capacity layer.
- Provider. San Diego Gas and Electric.
- URL. The SDG&E ICA map. Gated behind a free SDG&E account.
- Access. Manual download by the user. The file is dropped at data/raw, or the
  path is set with the SDGE_ICA_PATH env var. See README.
- Terms. Input only. The raw layer and its derived geometry are not
  redistributable. Confirm the exact SDG&E terms from the account portal and
  paste them here before any release.
- Redistributable. No.
- Handling. The raw file is gitignored. Derived geometry is written only to the
  gitignored data/interim path. Only feasibility flags that omit the raw load
  capacity values are written to committed processed outputs.

---

## Coverage limitation

The City of Los Angeles core served by LADWP is out of scope. LADWP is a
municipal utility. Its hosting capacity map uses a coarser grid and a different
methodology. Fusing it with the SCE and SDG&E investor owned utility layers would
mix methodologies. It is recorded here as a known coverage gap, not an omission.
