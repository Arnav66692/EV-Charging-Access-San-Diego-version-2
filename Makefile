# Phase 1 reproducibility targets. Each acquisition step is a target so the
# pipeline can be reproduced one step at a time. See README for prerequisites.

PY := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: help venv install test \
        afdc acs ces ces-relationship sce sdge osm join \
        access-centroids access-lodes access-gate access-primary \
        osrm-download osrm-build osrm-serve osrm-smoke clean

help:
	@echo "Targets:"
	@echo "  venv           create the Python 3.12 virtual environment"
	@echo "  install        install pinned dependencies into the venv"
	@echo "  test           run the pytest suite"
	@echo "  afdc           pull AFDC stations, write snapshot and processed tables"
	@echo "  acs            pull ACS block group demographics"
	@echo "  ces-relationship  build the population-weighted 2010 to 2020 relationship"
	@echo "  ces            crosswalk CalEnviroScreen 4.0 to 2020 block groups"
	@echo "  sce            pull the SCE DERiM grid layer"
	@echo "  sdge           read the user-dropped SDG&E ICA grid layer"
	@echo "  osm            pull OSM candidate sites"
	@echo "  join           join candidates to grid per territory"
	@echo "  access-centroids  build population weighted block group centroids"
	@echo "  access-lodes      build the LODES WAC DCFC demand layer"
	@echo "  access-gate       run the v1-compat San Diego gate, euclidean, no Docker"
	@echo "  access-primary    run primary drive time surfaces, needs live OSRM"
	@echo "  osrm-download  fetch the California OSM extract"
	@echo "  osrm-build     build the OSRM car profile with Docker"
	@echo "  osrm-serve     serve OSRM on port 5000"
	@echo "  osrm-smoke     run the OSRM San Diego smoke test"

venv:
	python3.12 -m venv .venv

install:
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

test:
	$(PY) -m pytest -q

afdc:
	$(PY) -m src.acquire.afdc

acs:
	$(PY) -m src.acquire.acs

ces-relationship:
	$(PY) -m src.acquire.ces_relationship

ces:
	$(PY) -m src.acquire.ces_crosswalk

sce:
	$(PY) -m src.acquire.sce_derim

sdge:
	$(PY) -m src.acquire.sdge_ica

osm:
	$(PY) -m src.acquire.osm_osrm

join:
	$(PY) -m src.join.candidate_grid_join

access-centroids:
	$(PY) -m src.access.centroids

access-lodes:
	$(PY) -m src.access.demand

access-gate:
	$(PY) -m src.access.run

access-primary:
	$(PY) -c "from src.access.run import run_primary; run_primary()"

osrm-download:
	bash scripts/build_osrm.sh download

osrm-build:
	bash scripts/build_osrm.sh build

osrm-serve:
	bash scripts/build_osrm.sh serve

osrm-smoke:
	$(PY) -m src.routing.osrm_client

clean:
	rm -rf data/interim/*.parquet data/processed/*.parquet
