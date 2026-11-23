#!/usr/bin/env bash
set -euo pipefail

# 5-minute reproducible Demo Pack runner for FIT4110 Lab 06 Plug-a-thon
# (Notification Service - Group 7, Pair 04: Core Business -> Notification).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LAB06_DIR="${REPO_ROOT}/06_Plugathon"
ENV_EXAMPLE_PATH="${LAB06_DIR}/.env.example"
ENV_PATH="${LAB06_DIR}/.env"
REPORTS_DIR="${LAB06_DIR}/reports"

CLEAN=0
SKIP_BUILD=0
SKIP_NEWMAN=0
NO_DLQ_RECOVERY=0
PORT_OVERRIDE=""
CREATED_TEMP_ENV=0

usage() {
  cat <<'EOF'
Usage: ./demo/run_demo.sh [OPTIONS]

Run the 5-minute end-to-end FIT4110 Lab 06 Plug-a-thon demo from a clean clone:
  1. Verify byte-for-byte SHA-256 parity of frozen v1.0.0 contracts.
  2. Validate standalone & external-broker Docker Compose configs.
  3. Lint OpenAPI 3.1 contract with Spectral.
  4. Start Compose stack (api + db + mqtt-broker) with temporary .env from .env.example.
  5. Verify non-root user (uid=10001), /health, and /ready.
  6. Run Pair-04 MQTT handshake, fault injection (DLQ/Q09/401/409/422), and /retry recovery.
  7. Run the 21-request Newman suite and emit HTML/XML reports.

Options:
  --clean            Tear down containers & volumes (`docker compose down -v`) on exit
  --skip-build       Skip `--build` when starting Compose
  --skip-newman      Skip npm install, Spectral lint, and Newman test run
  --no-dlq-recovery  Skip `--with-compose-dlq-recovery` transient fault + /retry test
  --port <PORT>      Override host port mapped to API port 8000
  -h, --help         Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --clean)
      CLEAN=1
      shift
      ;;
    --skip-build)
      SKIP_BUILD=1
      shift
      ;;
    --skip-newman)
      SKIP_NEWMAN=1
      shift
      ;;
    --no-dlq-recovery)
      NO_DLQ_RECOVERY=1
      shift
      ;;
    --port)
      if [[ $# -lt 2 || -z "$2" ]]; then
        echo "[ERROR] --port requires a numeric argument" >&2
        exit 2
      fi
      PORT_OVERRIDE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

log_step() {
  printf '\n==> %s\n' "$1"
}

find_python() {
  local candidate
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >/dev/null 2>&1; then
        printf '%s\n' "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

read_env_value() {
  local file_path="$1"
  local key="$2"
  local default_val="$3"
  local val=""
  if [[ -f "$file_path" ]]; then
    val="$(grep -E "^${key}=" "$file_path" | tail -n 1 | cut -d '=' -f 2- | tr -d '\r' || true)"
  fi
  if [[ -n "$val" ]]; then
    printf '%s\n' "$val"
  else
    printf '%s\n' "$default_val"
  fi
}

cleanup() {
  local exit_code=$?
  set +e
  if [[ "$CLEAN" -eq 1 ]]; then
    printf '\n==> Cleaning up Compose stack (--clean enabled)\n'
    (cd "$LAB06_DIR" && docker compose down -v) || true
  fi
  if [[ "$CREATED_TEMP_ENV" -eq 1 && -f "$ENV_PATH" ]]; then
    rm -f "$ENV_PATH"
    echo "[INFO] Removed temporary 06_Plugathon/.env."
  fi
  exit "$exit_code"
}
trap cleanup EXIT INT TERM

if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] docker is not installed or not in PATH." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "[ERROR] Docker daemon is not running or inaccessible." >&2
  exit 1
fi

PYTHON_BIN="$(find_python || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "[ERROR] Python 3.9+ (python3 or python) was not found in PATH." >&2
  exit 1
fi

if [[ "$SKIP_NEWMAN" -eq 0 ]] && ! command -v npm >/dev/null 2>&1; then
  echo "[ERROR] npm is not installed or not in PATH (pass --skip-newman to skip)." >&2
  exit 1
fi

START_SECONDS=$SECONDS
export PYTHONDONTWRITEBYTECODE=1

if [[ ! -f "$ENV_PATH" ]]; then
  cp "$ENV_EXAMPLE_PATH" "$ENV_PATH"
  CREATED_TEMP_ENV=1
  echo "[INFO] Created temporary 06_Plugathon/.env from .env.example (will be cleaned up on exit)."
else
  echo "[INFO] Using existing 06_Plugathon/.env (will be preserved on exit)."
fi

APP_PORT="${PORT_OVERRIDE:-$(read_env_value "$ENV_PATH" "APP_PORT" "8000")}"
MQTT_PORT="$(read_env_value "$ENV_PATH" "MQTT_PORT" "1883")"
AUTH_TOKEN_VAL="$(read_env_value "$ENV_PATH" "AUTH_TOKEN" "plugathon-dev-token")"

export APP_PORT
export AUTH_TOKEN="$AUTH_TOKEN_VAL"

BASE_URL="http://127.0.0.1:${APP_PORT}"
BROKER_URL="mqtt://127.0.0.1:${MQTT_PORT}"

log_step "1/6 Verifying frozen v1.0.0 contracts (SHA-256 parity)"
(cd "$LAB06_DIR" && "$PYTHON_BIN" scripts/verify_frozen_contracts.py)

log_step "2/6 Validating Compose configs (standalone + external class-net overlay)"
(
  cd "$LAB06_DIR"
  docker compose config --quiet
  docker compose -f docker-compose.yml -f docker-compose.external-broker.yml config --quiet
)
echo "[PASS] Both standalone and external-broker Compose configurations are valid."

if [[ "$SKIP_NEWMAN" -eq 0 ]]; then
  log_step "3/6 Ensuring Node tooling (Spectral + Newman) & linting OpenAPI 3.1 contract"
  (
    cd "$LAB06_DIR"
    if [[ ! -d node_modules ]]; then
      npm ci
    fi
    npm run lint:openapi
  )
else
  log_step "3/6 Skipping npm/OpenAPI lint (--skip-newman specified)"
fi

log_step "4/6 Starting 3-container Plug-a-thon stack (api + db + mqtt-broker)"
UP_FLAGS=(-d --wait)
if [[ "$SKIP_BUILD" -eq 0 ]]; then
  UP_FLAGS=(-d --build --wait)
fi
(
  cd "$LAB06_DIR"
  docker compose up "${UP_FLAGS[@]}"
  docker compose ps
  API_ID="$(docker compose exec -T api id | tr -d '\r')"
  if [[ "$API_ID" != *"uid=10001(appuser)"* ]]; then
    echo "[ERROR] Expected non-root uid=10001(appuser), got: $API_ID" >&2
    exit 1
  fi
  echo "[PASS] API container user verified: $API_ID"
)

log_step "5/6 Verifying /health and /ready endpoints"
"$PYTHON_BIN" - "$BASE_URL" <<'PY'
import json
import sys
import urllib.request

base_url = sys.argv[1].rstrip("/")

def fetch(path: str) -> dict:
    with urllib.request.urlopen(f"{base_url}{path}", timeout=5) as resp:
        assert resp.status == 200, f"GET {path} returned HTTP {resp.status}"
        return json.loads(resp.read().decode("utf-8"))

health = fetch("/health")
assert health.get("status") == "ok", f"Unexpected /health: {health}"
print(f"GET {base_url}/health ->")
print(json.dumps(health, ensure_ascii=False, indent=2))

ready = fetch("/ready")
deps = ready.get("dependencies", {})
assert ready.get("status") == "ready", f"Unexpected /ready: {ready}"
assert deps.get("database", {}).get("ready") is True, f"DB not ready: {ready}"
assert deps.get("mqtt", {}).get("connected") is True, f"MQTT not connected: {ready}"
print(f"GET {base_url}/ready ->")
print(json.dumps(ready, ensure_ascii=False, indent=2))
PY

log_step "6/6 Running Pair-04 E2E handshake, fault/DLQ injection & Newman verification"
E2E_ARGS=(scripts/run_plugathon_e2e.py --base-url "$BASE_URL" --broker "$BROKER_URL")
if [[ "$NO_DLQ_RECOVERY" -eq 0 ]]; then
  E2E_ARGS+=(--with-compose-dlq-recovery)
fi
(cd "$LAB06_DIR" && "$PYTHON_BIN" "${E2E_ARGS[@]}")

if [[ "$SKIP_NEWMAN" -eq 0 ]]; then
  mkdir -p "$REPORTS_DIR"
  if [[ "$APP_PORT" == "8000" && "$AUTH_TOKEN_VAL" == "plugathon-dev-token" ]]; then
    (cd "$LAB06_DIR" && npm run test:plugathon)
  else
    (
      cd "$LAB06_DIR"
      npm run test:plugathon -- \
        --env-var "baseUrl=http://localhost:${APP_PORT}" \
        --env-var "authToken=${AUTH_TOKEN_VAL}"
    )
  fi
fi

ELAPSED=$((SECONDS - START_SECONDS))
printf '\n============================================================\n'
printf ' FIT4110 Lab 06 Demo Pack — ALL CHECKS PASSED\n'
printf '============================================================\n'
printf ' Elapsed time : %ss (target <= 300s)\n' "$ELAPSED"
printf ' Demo UI      : %s/\n' "$BASE_URL"
printf ' Swagger UI   : %s/docs\n' "$BASE_URL"
printf ' Health/Ready : %s/health | %s/ready\n' "$BASE_URL" "$BASE_URL"
if [[ "$SKIP_NEWMAN" -eq 0 ]]; then
  printf ' Newman HTML  : 06_Plugathon/reports/newman-plugathon.html\n'
  printf ' Newman XML   : 06_Plugathon/reports/newman-plugathon.xml\n'
fi
if [[ "$CLEAN" -eq 1 ]]; then
  printf ' Cleanup mode : --clean enabled (stack will be torn down now)\n'
else
  printf ' Cleanup cmd  : docker compose -f 06_Plugathon/docker-compose.yml down -v\n'
fi
printf '============================================================\n'
