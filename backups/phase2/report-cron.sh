#!/bin/bash
set -euo pipefail
AGENT="/usr/local/bin/sec-agent"
LOG="/var/log/edge-sec-report.log"
SECRETS="/root/edge-sec-agent/secrets.env"
[ -f "$SECRETS" ] && source "$SECRETS"
mkdir -p "$(dirname "$LOG")"
if [ ! -x "$AGENT" ]; then echo "ERROR: sec-agent no encontrado" >> "$LOG"; exit 1; fi
OUTPUT="$("$AGENT" --security --json 2>&1)"
SCORE=$(echo "$OUTPUT" | jq -r '.score // 0')
RP=$(echo "$OUTPUT" | jq -r '.report_path // ""')
if [ -n "$RP" ] && [ "$RP" != "null" ]; then
    echo "$(date) - SUCCESS - $RP" >> "$LOG"
else
    echo "$(date) - JSON_ONLY - Score: $SCORE" >> "$LOG"
fi
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    if [ "${SEND_FULL_REPORT:-no}" = "yes" ] || [ -f /root/edge-sec-agent/send_full_report ]; then
        /usr/local/bin/telegram-notify.sh "$OUTPUT" 2>/dev/null
    elif [ "$SCORE" -lt 70 ]; then
        /usr/local/bin/telegram-notify.sh "Alerta: score $SCORE/100" 2>/dev/null
    fi
fi
