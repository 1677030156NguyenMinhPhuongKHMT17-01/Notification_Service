#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:4010}"
AUTH_HEADER="Authorization: Bearer test-token"

echo "[Lab02] Testing Notification Service Prism mock server at ${BASE_URL}"
echo

echo "[1/5] Happy path: GET /health"
curl -s -i "${BASE_URL}/health"
echo -e "\n---"

echo "[2/5] Happy path: GET /notifications/recent"
curl -s -i "${BASE_URL}/notifications/recent" -H "${AUTH_HEADER}"
echo -e "\n---"

echo "[3/5] Happy path: POST /notifications (alert.created snake_case)"
curl -s -i -X POST "${BASE_URL}/notifications" \
  -H "${AUTH_HEADER}" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "123e4567-e89b-12d3-a456-426614174000",
    "event_name": "alert.created",
    "correlationId": "req-0196fb3d-4ad7-7d1e-9f49-5d5148d2babc",
    "source": "core-business",
    "alert_id": "ALT-001",
    "severity": "high",
    "message": "Phat hien su co an ninh khan cap tu Core Business",
    "target_channels": ["telegram", "email", "sms"],
    "timestamp": "2026-08-27T15:30:00Z"
  }'
echo -e "\n---"

echo "[4/5] Error case: GET /notifications/recent without token (401 Unauthorized)"
curl -s -i "${BASE_URL}/notifications/recent"
echo -e "\n---"

echo "[5/5] Error case: POST /notifications invalid payload (422 Unprocessable Entity)"
curl -s -i -X POST "${BASE_URL}/notifications" \
  -H "${AUTH_HEADER}" \
  -H "Content-Type: application/json" \
  -d '{ "event_name": "alert.created", "severity": 12345 }'
echo
