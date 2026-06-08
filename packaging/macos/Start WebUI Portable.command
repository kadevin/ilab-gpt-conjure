#!/bin/zsh
set -e
set -o pipefail

BUNDLE_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="${BUNDLE_DIR}/app"
DATA_DIR="${BUNDLE_DIR}/data"
PYTHON_BIN="${BUNDLE_DIR}/python/Python.framework/Versions/3.11/bin/python3"
PORT="8787"
URL="http://127.0.0.1:${PORT}/"
HEALTH_URL="${URL}api/health"
WAIT_ATTEMPTS=60

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Portable Python was not found at ${PYTHON_BIN}."
  read -r "?Press Enter to close..."
  exit 1
fi

if [ ! -f "${APP_DIR}/portable_webui_app.py" ]; then
  echo "Portable app files were not found at ${APP_DIR}."
  read -r "?Press Enter to close..."
  exit 1
fi

mkdir -p "${DATA_DIR}/logs"
export ILAB_CONJURE_DATA_DIR="${DATA_DIR}"
export PYTHONPATH="${APP_DIR}:${APP_DIR}/.deps"
CERTIFI_CA_BUNDLE="${APP_DIR}/.deps/certifi/cacert.pem"
if [ -f "$CERTIFI_CA_BUNDLE" ]; then
  export SSL_CERT_FILE="$CERTIFI_CA_BUNDLE"
  export REQUESTS_CA_BUNDLE="$CERTIFI_CA_BUNDLE"
fi
LOG_FILE="${DATA_DIR}/logs/webui-server.log"

cd "$APP_DIR"

webui_is_ready() {
  "$PYTHON_BIN" - "$HEALTH_URL" <<'PY' >/dev/null 2>&1
import sys
from urllib.request import urlopen

with urlopen(sys.argv[1], timeout=0.5) as response:
    if response.status != 200:
        raise SystemExit(1)
PY
}

wait_for_webui() {
  local attempt=0
  while [ "$attempt" -lt "$WAIT_ATTEMPTS" ]; do
    if webui_is_ready; then
      return 0
    fi
    attempt=$((attempt + 1))
    sleep 0.5
  done
  return 1
}

echo "Starting iLab GPT Conjure at ${URL}"
echo "Data directory: ${DATA_DIR}"
echo "Writing server log to ${LOG_FILE}"

if webui_is_ready; then
  echo "WebUI is already running at ${URL}"
  open "$URL" >/dev/null 2>&1 || true
  exit 0
fi

"$PYTHON_BIN" -m uvicorn portable_webui_app:app --host 127.0.0.1 --port "$PORT" --no-access-log >> "$LOG_FILE" 2>&1 &
SERVER_PID="$!"

if wait_for_webui; then
  open "$URL" >/dev/null 2>&1 || true
else
  echo "WebUI did not become ready within 30 seconds. Check ${LOG_FILE}."
fi

wait "$SERVER_PID"
