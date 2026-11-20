#!/usr/bin/env bash
set -euo pipefail

HEALTH_URL="${EDGE_HEALTH_URL:-http://127.0.0.1:5000/v1/global/health}"
SERVICE_NAME="edge-sec-agent"
INSTALL_ROOT="${EDGE_INSTALL_ROOT:-/opt/edge-sec-agent}"
DB_PATH="${EDGE_DB_PATH:-$INSTALL_ROOT/data/history.db}"
REPORTS_DIR="${EDGE_REPORTS_DIR:-$INSTALL_ROOT/reports}"
SEC_AGENT_SCRIPT="${EDGE_SEC_AGENT_SCRIPT:-$INSTALL_ROOT/app/current/scripts/sec-agent}"
METRIC_COLLECTION="${EDGE_METRIC_COLLECTION:-1}"

collect_metric() {
  [[ "$METRIC_COLLECTION" == "1" ]] || return 0
  [[ -x "$SEC_AGENT_SCRIPT" ]] || return 0
  command -v runuser >/dev/null 2>&1 || return 0
  runuser -u edgesec -- env \
    EDGE_DB_PATH="$DB_PATH" \
    EDGE_REPORTS_DIR="$REPORTS_DIR" \
    "$SEC_AGENT_SCRIPT" --security --json >/dev/null 2>&1
}

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

collect_metric || true

if check_http && check_db && check_ports; then
  logger -t edge-sec-agent-health "health watchdog: ok"
  exit 0
fi

logger -t edge-sec-agent-health "health watchdog: fallo detectado, reiniciando $SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
exit 0
