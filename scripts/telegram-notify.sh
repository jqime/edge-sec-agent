#!/bin/bash
set -euo pipefail
if command -v /usr/local/bin/send_telegram.sh >/dev/null 2>&1; then
    /usr/local/bin/send_telegram.sh "$@" || true
    exit 0
fi
SECRETS="/root/edge-sec-agent/secrets.env"
[ -f "$SECRETS" ] && . "$SECRETS" >/dev/null 2>&1 || true
TOKEN="${TELEGRAM_BOT_TOKEN:-TU_TOKEN}"
CHAT_ID="${TELEGRAM_CHAT_ID:-TU_CHAT_ID}"
MSG="$*"
[ -z "$MSG" ] && exit 0
MAX_LEN=4096
if [ ${#MSG} -le $MAX_LEN ]; then
    curl -sS --max-time 10 -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" -d chat_id="$CHAT_ID" --data-urlencode "text=$MSG" >/dev/null 2>&1 || true
else
    TMP=$(mktemp); echo "$MSG" > "$TMP"
    curl -sS --max-time 10 -X POST "https://api.telegram.org/bot${TOKEN}/sendDocument" -F chat_id="$CHAT_ID" -F "document=@${TMP}" >/dev/null 2>&1 || true
    rm -f "$TMP"
fi
