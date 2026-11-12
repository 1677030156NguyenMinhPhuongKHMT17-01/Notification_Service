#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-local}"
COLLECTION="postman/collections/FIT4110_lab04_notification_docker.postman_collection.json"

mkdir -p reports

if [ "$MODE" = "mock" ]; then
  npx newman run "$COLLECTION" \
    -e postman/environments/FIT4110_lab04_mock.postman_environment.json \
    -r cli,junit,htmlextra \
    --reporter-junit-export reports/newman-lab04-mock.xml \
    --reporter-htmlextra-export reports/newman-lab04-mock.html
else
  npx newman run "$COLLECTION" \
    -e postman/environments/FIT4110_lab04_local.postman_environment.json \
    -r cli,junit,htmlextra \
    --reporter-junit-export reports/newman-lab04-local.xml \
    --reporter-htmlextra-export reports/newman-lab04-local.html
fi
