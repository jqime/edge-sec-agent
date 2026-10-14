#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Uso: $0 /ruta/backup-dir" >&2
  exit 2
fi

BACKUP_DIR="$1"
INSTALL_ROOT="${EDGE_INSTALL_ROOT:-/opt/edge-sec-agent}"
DATA_DIR="${EDGE_DATA_DIR:-$INSTALL_ROOT/data}"
REPORTS_DIR="${EDGE_REPORTS_DIR:-$INSTALL_ROOT/reports}"

if [[ ! -d "$BACKUP_DIR" ]]; then
  echo "Backup no encontrado: $BACKUP_DIR" >&2
  exit 1
fi

( cd "$BACKUP_DIR" && sha256sum -c SHA256SUMS )

mkdir -p "$DATA_DIR" "$REPORTS_DIR"

if [[ -f "$BACKUP_DIR/history.db" ]]; then
  cp "$BACKUP_DIR/history.db" "$DATA_DIR/history.db"
  python3 - <<PY
import sqlite3
path = "$DATA_DIR/history.db"
con = sqlite3.connect(path)
ok = con.execute("PRAGMA integrity_check;").fetchone()[0]
con.close()
if ok.lower() != "ok":
    raise SystemExit(f"SQLite integrity_check falló tras restaurar: {ok}")
PY
fi

if [[ -f "$BACKUP_DIR/reports.tar.gz" ]]; then
  tar -C "$REPORTS_DIR" -xzf "$BACKUP_DIR/reports.tar.gz"
fi

echo "Restore completado desde $BACKUP_DIR"
