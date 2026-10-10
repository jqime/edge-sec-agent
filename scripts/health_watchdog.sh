#!/usr/bin/env bash
set -euo pipefail

HEALTH_URL="${EDGE_HEALTH_URL:-http://127.0.0.1:5000/v1/global/health}"
SERVICE_NAME="edge-sec-agent"
INSTALL_ROOT="${EDGE_INSTALL_ROOT:-/opt/edge-sec-agent}"
DB_PATH="${EDGE_DB_PATH:-$INSTALL_ROOT/data/history.db}"

check_http() {
  curl --fail --silent --show-error --max-time 5 "$HEALTH_URL" >/dev/null
}

check_db() {
  [[ -f "$DB_PATH" ]] || return 0
  python3 - <<PY
import sqlite3
path = "$DB_PATH"
con = sqlite3.connect(path)
ok = con.execute("PRAGMA quick_check;").fetchone()[0]
con.close()
if ok.lower() != "ok":
    raise SystemExit(ok)
PY
}

check_ports() {
  ss -tln | grep -q '127.0.0.1:5000' || return 1
}

if check_http && check_db && check_ports; then
  logger -t edge-sec-agent-health "health watchdog: ok"
  exit 0
fi

logger -t edge-sec-agent-health "health watchdog: fallo detectado, reiniciando $SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
exit 0
