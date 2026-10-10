#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="${EDGE_INSTALL_ROOT:-/opt/edge-sec-agent}"
DATA_DIR="${EDGE_DATA_DIR:-$INSTALL_ROOT/data}"
REPORTS_DIR="${EDGE_REPORTS_DIR:-$INSTALL_ROOT/reports}"
BACKUPS_DIR="${EDGE_BACKUPS_DIR:-$INSTALL_ROOT/backups}"
RETENTION_DAYS="${EDGE_BACKUP_RETENTION_DAYS:-14}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
OUT_DIR="$BACKUPS_DIR/$STAMP"

mkdir -p "$OUT_DIR"

if [[ -f "$DATA_DIR/history.db" ]]; then
  cp "$DATA_DIR/history.db" "$OUT_DIR/history.db"
  python3 - <<PY
import sqlite3
path = "$OUT_DIR/history.db"
con = sqlite3.connect(path)
ok = con.execute("PRAGMA integrity_check;").fetchone()[0]
con.close()
if ok.lower() != "ok":
    raise SystemExit(f"SQLite integrity_check falló: {ok}")
PY
fi

if [[ -d "$REPORTS_DIR" ]]; then
  tar -C "$REPORTS_DIR" -czf "$OUT_DIR/reports.tar.gz" .
fi

cat > "$OUT_DIR/manifest.txt" <<MANIFEST
created_at_utc=$(date -u +%FT%TZ)
install_root=$INSTALL_ROOT
data_dir=$DATA_DIR
reports_dir=$REPORTS_DIR
MANIFEST

( cd "$OUT_DIR" && sha256sum * > SHA256SUMS )

find "$BACKUPS_DIR" -mindepth 1 -maxdepth 1 -type d -mtime +"$RETENTION_DAYS" -exec rm -rf {} +

echo "$OUT_DIR"
