$ErrorActionPreference = "Stop"

$BaseUrl = if ($env:BASE_URL) { $env:BASE_URL } else { "http://localhost:4010" }
$AuthHeader = "Authorization: Bearer test-token"

Write-Host "[Lab02] Testing Notification Service Prism mock server at $BaseUrl"
Write-Host ""

Write-Host "[1/5] Happy path: GET /health"
curl.exe -s -i "$BaseUrl/health"
Write-Host "`n---"

Write-Host "[2/5] Happy path: GET /notifications/recent"
curl.exe -s -i "$BaseUrl/notifications/recent" -H $AuthHeader
Write-Host "`n---"

Write-Host "[3/5] Happy path: POST /notifications (alert.created snake_case)"
$payload = '{
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
curl.exe -s -i -X POST "$BaseUrl/notifications" -H $AuthHeader -H "Content-Type: application/json" -d $payload
Write-Host "`n---"

Write-Host "[4/5] Error case: GET /notifications/recent without token (401 Unauthorized)"
curl.exe -s -i "$BaseUrl/notifications/recent"
Write-Host "`n---"

Write-Host "[5/5] Error case: POST /notifications invalid payload (422 Unprocessable Entity)"
curl.exe -s -i -X POST "$BaseUrl/notifications" -H $AuthHeader -H "Content-Type: application/json" -d '{ "event_name": "alert.created", "severity": 12345 }'
Write-Host ""
