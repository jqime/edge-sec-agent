#!/bin/bash
set -euo pipefail
SECRETS="/root/edge-sec-agent/secrets.env"
[ -f "$SECRETS" ] && source "$SECRETS"
TOKEN="${TELEGRAM_BOT_TOKEN:-}"
CHAT_ID="${TELEGRAM_CHAT_ID:-}"
if [ -z "$TOKEN" ] || [ -z "$CHAT_ID" ]; then
    echo "ERROR: faltan credenciales (revisa $SECRETS)" >&2
    exit 1
fi
MSG="$*"
[ -z "$MSG" ] && exit 1
if command -v jq >/dev/null && echo "$MSG" | jq -e . >/dev/null 2>&1; then
    SCORE=$(echo "$MSG" | jq -r '.score // 0')
    SSH=$(echo "$MSG" | jq -r '.ssh_failures // 0')
    PORTS=$(echo "$MSG" | jq -r '.open_ports | join(",") // ""')
    TEMP=$(echo "$MSG" | jq -r '.temp_c // 0')
    RAM=$(echo "$MSG" | jq -r '.ram_percent // 0')
    TEXT="Informe Seguridad\nScore: $SCORE\nSSH: $SSH\nPuertos: $PORTS\nTemp: $TEMP°C\nRAM: $RAM%"
else
    TEXT="$MSG"
fi
if [ ${#TEXT} -le 4000 ]; then
    curl -sS --max-time 10 -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" -d chat_id="$CHAT_ID" --data-urlencode "text=$TEXT" >/dev/null
else
    TMP=$(mktemp)
    echo "$TEXT" > "$TMP"
    curl -sS --max-time 10 -X POST "https://api.telegram.org/bot${TOKEN}/sendDocument" -F chat_id="$CHAT_ID" -F "document=@$TMP" >/dev/null
    rm -f "$TMP"
fi
