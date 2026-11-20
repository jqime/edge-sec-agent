#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
SEND_TELEGRAM="$SCRIPT_DIR/send_telegram.sh"
if [ -x "$SEND_TELEGRAM" ]; then
    "$SEND_TELEGRAM" "$@" || true
    exit 0
fi
SECRETS="$PROJECT_ROOT/secrets.env"
if [ -f "$SECRETS" ]; then
    set +eu
    . "$SECRETS" >/dev/null 2>&1 || true
    set -eu
fi
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
