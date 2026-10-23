# Code license and data provenance

The author's code is licensed under [MIT](LICENSE). MIT does not apply to
third-party datasets. A public download URL is not itself a redistribution grant.

| Source | Attribution and source | Repository handling |
| --- | --- | --- |
| AFDC | U.S. DOE Alternative Fuels Data Center; [API docs](https://developer.nrel.gov/docs/transportation/alt-fuel-stations-v1/) | Small snapshot fixtures and derived results; keep source attribution |
| ACS / TIGER | U.S. Census Bureau, ACS 2019–2023 five-year estimates; [Census](https://www.census.gov/data.html) | Derived demographic values and boundaries |
| CalEnviroScreen 4.0 | OEHHA and CalEPA; [release](https://oehha.ca.gov/calenviroscreen/report/calenviroscreen-40) | Crosswalked estimates; not an official DAC designation |
| OpenStreetMap | © OpenStreetMap contributors; [ODbL terms](https://www.openstreetmap.org/copyright) | Candidate sites and routing inputs; preserve attribution and applicable database obligations |
| SCE DERiM | Southern California Edison; [ICA Circuit Segments](https://drpep-sce2.opendata.arcgis.com/datasets/SCE2::ica-circuit-segments) | Local source layer and derived screening results; portal terms govern reuse |
| SDG&E ICA | San Diego Gas & Electric account-based ICA portal | User-supplied input only; raw geometry and load-capacity values remain local |

This product uses the NREL API but is not endorsed or certified by NREL.
Source agencies and utilities do not endorse the modeled results. Grid hosting
capacity is informational and does not guarantee an interconnection outcome.

## Distribution boundary

Full `data/raw`, `data/interim`, and `data/processed` tables are not distributed.
The web map ships derived block-group metrics, county boundaries and candidate
tier classifications. Schema tests prohibit raw SDG&E load-capacity fields in
public map data. Gitignore is a convenience, not a licensing enforcement mechanism.

The repository does not include a verified grant to republish the OEHHA, SCE or
SDG&E source layers under MIT. Obtain those layers from their source portals
under the applicable terms. Do not infer unrestricted redistribution rights from
this document. The previous blanket “redistributable: yes” assertions and
instructions to paste unseen account terms have been removed.

## Coverage

The LADWP-served Los Angeles core is outside the utility-grid scope. County
boundaries are an approximation, not a utility service-territory guarantee.
