#!/bin/bash
set -euo pipefail
SECRETS="/root/edge-sec-agent/secrets.env"
ALERTS_CONFIG="/root/edge-sec-agent/alerts.json"
[ -f "$SECRETS" ] && . "$SECRETS" >/dev/null 2>&1 || true
TOKEN="${TELEGRAM_BOT_TOKEN:-TU_TOKEN}"
CHAT_ID="${TELEGRAM_CHAT_ID:-TU_CHAT_ID}"
MSG="$*"
[ -z "$MSG" ] && exit 0
MAX_LEN=4096
is_json=0
command -v jq >/dev/null && echo "$MSG" | jq -e . >/dev/null 2>&1 && is_json=1
send_text() { curl -sS --max-time 10 -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" -d chat_id="$CHAT_ID" --data-urlencode "text=$1" >/dev/null 2>&1 || true; }
send_document() { local file="$1"; curl -sS --max-time 10 -X POST "https://api.telegram.org/bot${TOKEN}/sendDocument" -F chat_id="$CHAT_ID" -F "document=@${file}" >/dev/null 2>&1 || true; rm -f "$file"; }
if [ $is_json -eq 1 ]; then
    SCORE=$(echo "$MSG" | jq -r '.score//0')
    SSH=$(echo "$MSG" | jq -r '.ssh_failures//0')
    PORTS=$(echo "$MSG" | jq -r '.open_ports|join(",")//""')
    TEMP=$(echo "$MSG" | jq -r '.temp_c//0')
    RAM=$(echo "$MSG" | jq -r '.ram_percent//0')
    TEXT="Informe de Seguridad\nScore: $SCORE\nSSH: $SSH\nPuertos: $PORTS\nTemp: ${TEMP}C\nRAM: ${RAM}%"
else
    TEXT="$MSG"
fi
if [ ${#TEXT} -le $MAX_LEN ]; then send_text "$TEXT"
else TMP=$(mktemp); printf "%s" "$TEXT" > "$TMP"; send_document "$TMP"; fi
