# EV grid siting, Phase 1

Grid constrained, equity aware analysis of EV fast charging accessibility and
siting across two California utility territories. This repository is Phase 1
only. Phase 1 assembles and joins the data and stands up routing. It does not
score accessibility, model queues, or optimize siting. Those are later phases.

## What Phase 1 delivers

- AFDC charging stations for California, frozen as a dated snapshot.
- ACS block group demographics for the three in-scope counties.
- CalEnviroScreen 4.0 disadvantaged community flags, crosswalked to 2020 tracts.
- SCE DERiM grid hosting capacity line sections.
- SDG&E ICA grid hosting capacity line sections, read from a user file.
- OSM candidate sites for charger siting.
- A candidate to grid spatial join, per territory, carrying load capacity.
- An OSRM drive time service with a Python client and a smoke test.

## Scope

In scope. SDG&E territory in San Diego County, FIPS 06073. SCE territory across
Orange County, FIPS 06059, and Los Angeles County, FIPS 06037.

Out of scope. The City of Los Angeles core served by LADWP. LADWP is a municipal
utility with a coarser hosting capacity map on a different methodology. It is not
fused here. See the coverage limitation in LICENSING.md.

## Coordinate reference systems

Geometries are stored in EPSG:4326. All distance and join work projects to
EPSG:3310, California Albers, which is an equal area meters CRS. This is set in
config.yaml and applied in the join.

## Repository layout

```
ev-grid-siting/
  README.md  LICENSING.md  requirements.txt  config.yaml  .gitignore  Makefile
  data/
    raw/         input only, gitignored, holds the SDG&E file and OSM extract
    interim/     scratch and SDG&E derived geometry, gitignored
    processed/   committed redistributable outputs
    snapshots/   frozen AFDC snapshots
  src/
    config.py            config and secrets loader, FIPS helpers
    utils.py             sha256, manifests, small helpers
    acquire/
      afdc.py            AFDC stations and ports, snapshot and manifest
      acs.py             ACS block group demographics
      ces_relationship.py  population weighted 2010 to 2020 relationship builder
      ces_crosswalk.py   CES 4.0 to 2020 block groups, population weighted
      sce_derim.py       SCE DERiM ICA grid layer, paginated ArcGIS query
      sdge_ica.py        SDG&E ICA grid layer, input only
      osm_osrm.py        OSM candidate sites and the OSRM extract download
    join/
      candidate_grid_join.py   candidate to grid nearest join per territory
    routing/
      osrm_client.py     thin OSRM drive time and distance client
  tests/                 pytest suite
  manifests/             reproducibility manifests
  docs/grid_fields.md    which SCE ICA field is the load value, and why
  scripts/build_osrm.sh  OSRM build and serve with Docker
```

The SCE ICA load field used for feasibility is ica_overall_load, the binding
minimum load value. The most_limiting_factor field on that layer is generation
oriented, so it is carried as generation_limiting_factor, not as a load
constraint. The full confirmation is in docs/grid_fields.md.

## Setup

Phase 1 is built and tested on Python 3.12. Use a virtual environment.

```
make venv
make install
```

Or do it by hand.

```
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

## Secrets and environment variables

Copy the example file and fill in your keys. The .env file is gitignored. Never
commit keys.

```
cp .env.example .env
```

| Variable | Purpose | Required for |
| --- | --- | --- |
| NREL_API_KEY | NREL AFDC stations API | AFDC pull |
| CENSUS_API_KEY | Census ACS API | ACS pull |
| SDGE_ICA_PATH | Path to the SDG&E ICA file | SDG&E read, optional |
| OSRM_BASE_URL | OSRM instance URL | Routing, defaults to localhost:5000 |

Request an NREL key at https://developer.nrel.gov/signup/. Request a Census key
at https://api.census.gov/data/key_signup.html.

## Where to drop the SDG&E file

The SDG&E ICA map is gated behind a free SDG&E account. It is input only and is
not redistributable. Download the line section layer from the SDG&E ICA map.
Save it to one of these.

- The default path, data/raw/sdge_ica.geojson.
- Any path, then set SDGE_ICA_PATH to that path in your .env.

The reader accepts any format geopandas can open, including GeoJSON, shapefile,
geopackage, and file geodatabase. The raw file stays gitignored. Its derived
geometry is written only to gitignored interim. See LICENSING.md.

## Reproduce each step

Each step is a Make target. Run them in this order. Steps are independent except
the join, which needs the candidate sites and both grid layers first.

```
make afdc              # pull AFDC, write snapshot, sha256, manifest, processed tables
make acs               # pull ACS block groups for the three counties
make ces-relationship  # build the population weighted 2010 to 2020 relationship
make ces               # crosswalk CES 4.0 to 2020 block groups, report coverage
make sce               # pull the SCE DERiM ICA grid layer
make sdge              # read the user-dropped SDG&E ICA grid layer
make osm               # pull OSM candidate sites
make join              # join candidates to grid, per territory
make test              # run the test suite
```

Without Make, call the modules directly.

```
.venv/bin/python -m src.acquire.afdc
.venv/bin/python -m src.acquire.acs
.venv/bin/python -m src.acquire.ces_relationship
.venv/bin/python -m src.acquire.ces_crosswalk
.venv/bin/python -m src.acquire.sce_derim
.venv/bin/python -m src.acquire.sdge_ica
.venv/bin/python -m src.acquire.osm_osrm
.venv/bin/python -m src.join.candidate_grid_join
```

### CES crosswalk inputs

The CES step needs two inputs in place first.

- The CES 4.0 release from OEHHA, saved at data/raw/ces40.xlsx or data/raw/ces40.csv.
- The population weighted 2010 to 2020 relationship table at
  data/interim/tract_rel_2010_2020.csv. This is built for you. Run
  make ces-relationship, or python -m src.acquire.ces_relationship.

The relationship builder is automated. It uses two official Census bulk files,
neither needs an API key. The first is the 2020 P.L. 94-171 block population,
table P1 field P0010001. The second is the 2010 to 2020 tabulation block
relationship file. The atom is the 2020 Census block. Each 2020 block has a 2020
population, nests in one 2010 tract, and nests in one 2020 block group. The
weight is real 2020 block population, summed by the pair of 2010 tract and 2020
block group. Land area is used only to assign a block to its dominant 2010 tract,
never as a population weight. The crosswalk then weights the 2010 tract CES
percentile onto each 2020 block group by that population.

The builder downloads about 90 MB the first time, to data/raw, which is
gitignored. For the three in-scope counties the output is roughly 10800 tract to
block group pairs covering about 10700 block groups.

## AFDC snapshot and reproducibility

AFDC changes daily. Each AFDC pull writes a dated snapshot to data/snapshots, a
sha256 of the exact bytes, and a manifest in manifests with the query parameters
and the pull date. The snapshot is the record of record for a future Zenodo
deposit. A sample snapshot and manifest are committed as a fixture. The snapshot
test recomputes the sha256 and checks it against the manifest.

## OSRM routing

OSRM serves drive time and drive distance. Build it with Docker.

```
make osrm-download   # fetch the California extract from Geofabrik
make osrm-build      # extract, partition, customize with the car profile
make osrm-serve      # serve on http://localhost:5000
make osrm-smoke      # run the San Diego smoke test
```

Storage. The California extract is roughly 1 GB. The processed OSRM files add
several GB. Budget about 10 GB free on the data volume. The extract and the OSRM
build files are gitignored.

RAM. The extract step on California needs a few GB. Budget 8 GB to be safe. This
build uses the MLD algorithm, which is light at query time.

Client. src/routing/osrm_client.py returns drive time and drive distance for a
pair or a small batch. Coordinates are lon, lat. The smoke test routes a few
known San Diego pairs and checks for positive finite drive times.

## Tests

```
make test
```

The suite checks the Phase 1 invariants.

- FIPS columns are strings with leading zeros preserved.
- The candidate to grid join leaves zero candidates silently unjoined.
- The AFDC snapshot matches its recorded sha256.
- The CES crosswalk assigns a DAC percentile to every in-scope block group, or
  the gap is listed.
- The OSRM client returns positive finite drive times for the smoke test pairs.

The suite runs fully offline on small fixtures. It needs no keys, no network, and
no Docker.

## Outputs

Committed, redistributable, under data/processed.

- afdc_stations.parquet, afdc_ports.parquet
- acs_blockgroups.parquet
- ces_dac_blockgroups.parquet
- sce_derim_grid.parquet
- candidate_sites.parquet
- joined_candidates_sce.parquet
- sdge_candidate_feasibility.parquet, feasibility flags only

Gitignored, input only, under data/interim.

- sdge_ica_grid.parquet
- joined_candidates_sdge.parquet, carries SDG&E load capacity values

## Licensing

Licensing is asymmetric and enforced from the start. AFDC, ACS, CalEnviroScreen,
OpenStreetMap, and SCE DERiM are redistributable. The SDG&E ICA layer is input
only and is gitignored. See LICENSING.md for the per source terms and attribution
strings.

## What Phase 1 does not do

Phase 1 stops at acquisition, the join, and routing. It does not build the
accessibility scoring, the queueing model, or the siting optimizer. Those are
Phase 2 and later.
