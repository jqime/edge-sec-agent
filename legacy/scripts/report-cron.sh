#!/bin/bash
set -euo pipefail
AGENT="/usr/local/bin/sec-agent"
LOG="/var/log/edge-sec-report.log"
ROOT="/root/edge-sec-agent"
SECRETS="$ROOT/secrets.env"
ALERTS_JSON="$ROOT/alerts.json"
[ -f "$SECRETS" ] && . "$SECRETS" >/dev/null 2>&1 || true
mkdir -p "$(dirname "$LOG")"
[ ! -x "$AGENT" ] && { echo "$(date) - ERROR: sec-agent no encontrado" | tee -a "$LOG"; exit 1; }
OUTPUT="$("$AGENT" --security --json 2>&1)"
if command -v jq >/dev/null 2>&1; then
    SCORE=$(echo "$OUTPUT" | jq -r '.score // 0')
    REPORT_PATH=$(echo "$OUTPUT" | jq -r '.report_path // ""')
else
    SCORE=$(echo "$OUTPUT" | grep -oE '"score":[0-9]+' | cut -d: -f2)
    REPORT_PATH=""
fi
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
if [ -n "$REPORT_PATH" ] && [ "$REPORT_PATH" != "null" ]; then
    echo "$TIMESTAMP - SUCCESS - $REPORT_PATH" >> "$LOG"
else
    echo "$TIMESTAMP - JSON_ONLY - Score: $SCORE" >> "$LOG"
fi
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    if [ "${SEND_FULL_REPORT:-no}" = "yes" ] || [ -f "$ROOT/send_full_report" ]; then
        /usr/local/bin/telegram-notify.sh "$OUTPUT" 2>/dev/null || true
    elif [ -n "$SCORE" ] && [ "$SCORE" -lt 70 ]; then
        /usr/local/bin/telegram-notify.sh "⚠️ Alerta: puntuación $SCORE/100" 2>/dev/null || true
    fi
fi
echo "Score: $SCORE"
echo "Informe: $REPORT_PATH" >> "$LOG"
