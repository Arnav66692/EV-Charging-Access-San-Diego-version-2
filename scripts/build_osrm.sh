#!/usr/bin/env bash
# Build and serve a California car-profile OSRM instance with Docker.
#
# Storage. The California extract is roughly 1 GB. The processed OSRM files add
# several GB. Budget about 10 GB free on the data volume.
# RAM. osrm-extract on California needs a few GB. The MLD pipeline used here is
# lighter at query time than contraction hierarchies. Budget 8 GB to be safe.
#
# Usage:
#   scripts/build_osrm.sh download   # fetch the Geofabrik extract
#   scripts/build_osrm.sh build      # extract, partition, customize
#   scripts/build_osrm.sh serve      # run osrm-routed on port 5000
#   scripts/build_osrm.sh all        # download then build

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${REPO_ROOT}/data/raw"
PBF="california-latest.osm.pbf"
BASENAME="california-latest"
IMAGE="ghcr.io/project-osrm/osrm-backend:latest"
EXTRACT_URL="https://download.geofabrik.de/north-america/us/california-latest.osm.pbf"

download() {
  mkdir -p "${DATA_DIR}"
  echo "Downloading California extract to ${DATA_DIR}/${PBF}"
  curl -L --fail -o "${DATA_DIR}/${PBF}" "${EXTRACT_URL}"
}

build() {
  if [ ! -f "${DATA_DIR}/${PBF}" ]; then
    echo "Missing ${DATA_DIR}/${PBF}. Run: scripts/build_osrm.sh download" >&2
    exit 1
  fi
  echo "Extracting with the car profile"
  docker run -t -v "${DATA_DIR}:/data" "${IMAGE}" \
    osrm-extract -p /opt/car.lua "/data/${PBF}"
  echo "Partitioning"
  docker run -t -v "${DATA_DIR}:/data" "${IMAGE}" \
    osrm-partition "/data/${BASENAME}.osrm"
  echo "Customizing"
  docker run -t -v "${DATA_DIR}:/data" "${IMAGE}" \
    osrm-customize "/data/${BASENAME}.osrm"
  echo "Build complete."
}

serve() {
  echo "Serving OSRM on http://localhost:5000 with the MLD algorithm"
  docker run -t -i -p 5000:5000 -v "${DATA_DIR}:/data" "${IMAGE}" \
    osrm-routed --algorithm mld "/data/${BASENAME}.osrm"
}

case "${1:-all}" in
  download) download ;;
  build) build ;;
  serve) serve ;;
  all) download && build ;;
  *) echo "Usage: $0 {download|build|serve|all}" >&2; exit 1 ;;
esac
