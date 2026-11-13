#!/usr/bin/env bash
set -euo pipefail

COLLECTION="${COLLECTION:-postman/collections/FIT4110_lab03_notification.postman_collection.json}"
case "${1:-mock}" in
  mock)
    ENVIRONMENT="postman/environments/FIT4110_lab03_mock.postman_environment.json"
    ;;
  local)
    ENVIRONMENT="postman/environments/FIT4110_lab03_local.postman_environment.json"
    ;;
  *)
    ENVIRONMENT="${1}"
    ;;
esac

mkdir -p reports

npx newman run "${COLLECTION}" \
  -e "${ENVIRONMENT}" \
  --reporters cli,junit,htmlextra \
  --reporter-junit-export reports/newman-report.xml \
  --reporter-htmlextra-export reports/newman-report.html
