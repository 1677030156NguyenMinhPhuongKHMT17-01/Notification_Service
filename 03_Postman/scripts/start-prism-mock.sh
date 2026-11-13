#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-notify}"

case "${MODE}" in
  notify)
    npx prism mock contracts/notification.openapi.yaml -p 4010 --host 0.0.0.0
    ;;
  core)
    npx prism mock contracts/core-business.openapi.yaml -p 4011 --host 0.0.0.0
    ;;
  all)
    npm run mock:notify &
    NOTIFY_PID=$!
    npm run mock:core &
    CORE_PID=$!
    trap 'kill ${NOTIFY_PID} ${CORE_PID} 2>/dev/null || true' EXIT
    wait
    ;;
  *)
    echo "Usage: scripts/start-prism-mock.sh [notify|core|all]"
    exit 1
    ;;
esac
