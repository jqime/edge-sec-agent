#!/bin/bash
set -euo pipefail

AGENT="/usr/local/bin/sec-agent"
LOG="/var/log/edge-sec-report.log"

# Cargar secretos de Telegram y opcionales
SECRETS="/etc/edge-sec-agent/secrets.env"
[ -f "$SECRETS" ] && source "$SECRETS" 2>/dev/null || true

mkdir -p "$(dirname "$LOG")"

if [ ! -x "$AGENT" ]; then
    echo "$(date) - ERROR: sec-agent no encontrado" >> "$LOG"
    exit 1
fi

OUTPUT="$("$AGENT" --security --json 2>&1)"
SCORE=$(echo "$OUTPUT" | jq -r '.score // 0')
RP=$(echo "$OUTPUT" | jq -r '.report_path // ""')

if [ -n "$RP" ] && [ "$RP" != "null" ]; then
    echo "$(date) - SUCCESS - $RP" >> "$LOG"
else
    echo "$(date) - JSON_ONLY - Score: $SCORE" >> "$LOG"
fi

# Enviar a Telegram si hay credenciales
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    if [ "${SEND_FULL_REPORT:-no}" = "yes" ] || [ -f /etc/edge-sec-agent/send_full_report ]; then
        /usr/local/bin/telegram-notify.sh "$OUTPUT" 2>/dev/null
    elif [ "$SCORE" -lt 70 ]; then
        /usr/local/bin/telegram-notify.sh "Alerta: puntuación $SCORE/100" 2>/dev/null
    fi
fi

# Correo (si se define ALERT_EMAIL en secrets.env)
if [ -n "${ALERT_EMAIL:-}" ]; then
    echo "$OUTPUT" | mailx -s "Edge Sec Report" "$ALERT_EMAIL" 2>/dev/null || true
fi

exit 0
