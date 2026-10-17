#!/bin/bash
# cowrie_alert.sh — Lee el log JSON de Cowrie y envía alertas a Telegram (anti-spam por IP).
# Rutas derivadas del propio fichero; secretos fuera de Git (SECRETS_PATH o <repo>/secrets.env).
set -Eeuo pipefail
export LC_ALL=C

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"

COWRIE_LOG="${COWRIE_LOG:-/opt/cowrie/cowrie-git/var/log/cowrie/cowrie.json}"
STATE_DIR="${COWRIE_ALERT_STATE_DIR:-$PROJECT_ROOT/data}"
STATE_FILE="$STATE_DIR/cowrie_alert.state"
SEEN_FILE="$STATE_DIR/cowrie_alert.seen"
LOCK_FILE="$STATE_DIR/cowrie_alert.lock"
SECRETS="${SECRETS_PATH:-$PROJECT_ROOT/secrets.env}"
SUPPRESS_SECONDS="${COWRIE_ALERT_SUPPRESS:-300}"
MAX_LEN=4096

log() { printf '%s cowrie_alert: %s\n' "$(date -Is)" "$*" >&2; }

[ -f "$COWRIE_LOG" ] || { log "log de Cowrie no encontrado: $COWRIE_LOG"; exit 0; }
command -v python3 >/dev/null || { log "python3 no disponible"; exit 1; }
mkdir -p "$STATE_DIR"

exec 9>"$LOCK_FILE"
flock -n 9 || { log "ya en ejecución (lock); salgo"; exit 0; }

if [ -f "$SECRETS" ]; then
    set +eu
    . "$SECRETS" >/dev/null 2>&1 || true
    set -eu
fi
TOKEN="${TELEGRAM_BOT_TOKEN:-}"
CHAT_ID="${TELEGRAM_CHAT_ID:-}"

send_telegram() {
    local text="$1"
    if [ -z "$TOKEN" ] || [ -z "$CHAT_ID" ]; then
        log "Telegram sin configurar (TOKEN/CHAT_ID vacíos); no envío"
        return 0
    fi
    local resp
    if [ "${#text}" -le "$MAX_LEN" ]; then
        resp="$(curl -sS --max-time 10 -X POST \
            "https://api.telegram.org/bot${TOKEN}/sendMessage" \
            -d chat_id="$CHAT_ID" --data-urlencode "text=$text" 2>&1)" || true
    else
        local tmp; tmp="$(mktemp)"
        printf '%s' "$text" > "$tmp"
        resp="$(curl -sS --max-time 10 -X POST \
            "https://api.telegram.org/bot${TOKEN}/sendDocument" \
            -F chat_id="$CHAT_ID" -F "document=@${tmp}" 2>&1)" || true
        rm -f "$tmp"
    fi
    if [ "${COWRIE_ALERT_DEBUG:-0}" = "1" ]; then
        log "telegram resp: ${resp}"
    fi
}

OFFSET=0
[ -f "$STATE_FILE" ] && OFFSET="$(cat "$STATE_FILE" 2>/dev/null || echo 0)"
SIZE="$(stat -c '%s' "$COWRIE_LOG" 2>/dev/null || echo 0)"
[ "$SIZE" -lt "$OFFSET" ] && OFFSET=0

NEW_OFFSET_TMP="$(mktemp)"
trap 'rm -f "$NEW_OFFSET_TMP"' EXIT
mapfile -t EVENTS < <(python3 - "$COWRIE_LOG" "$OFFSET" "$NEW_OFFSET_TMP" <<'PY'
import json
import sys

log_path, offset, out_path = sys.argv[1], int(sys.argv[2]), sys.argv[3]
INTERESTING = {
    "cowrie.session.connect",
    "cowrie.login.failed",
    "cowrie.login.success",
    "cowrie.command.input",
}

pos = offset
with open(log_path, "rb") as fh:
    fh.seek(offset)
    for raw in fh.readlines():
        pos += len(raw)
        line = raw.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            continue
        eventid = event.get("eventid", "")
        src_ip = event.get("src_ip", "")
        if eventid not in INTERESTING or not src_ip:
            continue
        detail = event.get("input") or event.get("username") or event.get("session") or ""
        ts = event.get("timestamp", "")
        print(f"{src_ip}\t{eventid}\t{ts}\t{detail}")

with open(out_path, "w", encoding="utf-8") as out:
    out.write(str(pos))
PY
)

NEXT_OFFSET="$(cat "$NEW_OFFSET_TMP" 2>/dev/null || echo "$OFFSET")"
printf '%s\n' "$NEXT_OFFSET" > "$STATE_FILE"

NOW="$(date +%s)"
ALERTED=0
for ev in "${EVENTS[@]:-}"; do
    [ -n "$ev" ] || continue
    IFS=$'\t' read -r ip eventid ts detail <<< "$ev"
    [ -n "$ip" ] || continue

    if [ -f "$SEEN_FILE" ] && awk -v ip="$ip" -v now="$NOW" -v win="$SUPPRESS_SECONDS" \
        '$1==ip { if (now-$2 < win) found=1 } END { exit(found?0:1) }' "$SEEN_FILE"; then
        continue
    fi

    printf '%s %s\n' "$ip" "$NOW" >> "$SEEN_FILE"
    send_telegram "Honeypot Cowrie — amenaza detectada
Evento: ${eventid}
Origen: ${ip}
Detalle: ${detail:-n/d}
Hora: ${ts}
Sensor: Orange Pi Zero 3 (:2223)"
    ALERTED=$((ALERTED + 1))
done

if [ "$ALERTED" -gt 0 ]; then
    log "alertas enviadas: $ALERTED"
else
    log "sin alertas nuevas (eventos procesados: ${#EVENTS[@]})"
fi

# Podar entradas antiguas del registro de supresión.
if [ -f "$SEEN_FILE" ]; then
    awk -v now="$NOW" -v win="$SUPPRESS_SECONDS" '$2 >= now-win' "$SEEN_FILE" > "${SEEN_FILE}.tmp" 2>/dev/null || true
    mv -f "${SEEN_FILE}.tmp" "$SEEN_FILE" 2>/dev/null || true
fi
