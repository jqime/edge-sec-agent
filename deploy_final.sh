#!/bin/bash
# edge-sec-agent: despliegue único para corregir wrapper, main(), notificaciones y secrets.
set -euo pipefail

ROOT="/root/edge-sec-agent"
WRAPPER="/usr/local/bin/sec-agent"
AGENT_PY="$ROOT/src/agent.py"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$ROOT/backups/${TIMESTAMP}"
mkdir -p "$BACKUP_DIR"

backup_if_exists() {
  local f="$1"
  if [ -f "$f" ]; then
    cp -p "$f" "$BACKUP_DIR/"
    echo "[BACKUP] $f -> $BACKUP_DIR/"
  else
    echo "[INFO] No existe $f para respaldar."
  fi
}
backup_if_exists "$WRAPPER"
backup_if_exists "$AGENT_PY"
backup_if_exists "/usr/local/bin/telegram-notify.sh" 2>/dev/null || true
backup_if_exists "/usr/local/bin/report-cron.sh" 2>/dev/null || true

# 1) Wrapper sec-agent
cat > "$WRAPPER" << 'WRAPPER_EOF'
#!/bin/bash
set -euo pipefail
AGENT_PY="/root/edge-sec-agent/src/agent.py"
if [[ "$*" =~ (^|[[:space:]])(--security|--json)([[:space:]]|$) ]]; then
  exec python3 "$AGENT_PY" "$@"
fi
LOW=$(echo "$*" | tr '[:upper:]' '[:lower:]')
case "$LOW" in
  *red*|*dispositivos*|*arp*)            exec /usr/local/bin/sec red ;;
  *puertos*|*ports*)                     exec /usr/local/bin/sec puertos ;;
  *ram*|*memoria*)                       exec /usr/local/bin/sec ram ;;
  *temp*|*temperatura*)                  exec /usr/local/bin/sec temp ;;
  *status*|*estado*|*kernel*|*logs*|*servicio*|*reiniciar*|*firewall*|*fail2ban*|*docker*|*actualizar*|*update*)
                                         exec /usr/local/bin/sec status ;;
  *)                                     exec python3 "$AGENT_PY" "$@" ;;
esac
WRAPPER_EOF
chmod +x "$WRAPPER"
echo "[OK] Wrapper sec-agent actualizado."

# 2) Parchear main() en agent.py
python3 - << 'PY'
from pathlib import Path
p = Path("/root/edge-sec-agent/src/agent.py")
if p.exists():
    txt = p.read_text()
    if "json_output" not in txt:
        anchor = "args = sys.argv[1:]"
        patch = anchor + "\n\n    json_output = \"--json\" in args\n    if \"--security\" in args:\n        cmd_security(json_output=json_output)\n        return"
        txt = txt.replace(anchor, patch)
        p.write_text(txt)
        print("OK: main() parcheado.")
    else:
        print("INFO: main() ya tiene json_output.")
PY

# 3) telegram-notify.sh (completo)
cat > /usr/local/bin/telegram-notify.sh << 'TELE'
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
TELE
chmod +x /usr/local/bin/telegram-notify.sh

# 4) report-cron.sh
cat > /usr/local/bin/report-cron.sh << 'REPORT'
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
REPORT
chmod +x /usr/local/bin/report-cron.sh

# 5) Archivo de secretos (con placeholders)
cat > "/root/edge-sec-agent/secrets.env" << 'SEC'
TELEGRAM_BOT_TOKEN="TU_TOKEN_AQUI"
TELEGRAM_CHAT_ID="TU_CHAT_ID_AQUI"
SEND_FULL_REPORT=yes
SEC
chmod 600 "/root/edge-sec-agent/secrets.env"

# 6) Asegurar timer systemd
systemctl daemon-reload
systemctl enable sec-report.timer 2>/dev/null || true
systemctl start sec-report.timer 2>/dev/null || true

# 7) Prueba final
echo "=== Prueba JSON ==="
sec-agent --security --json | jq .
echo "=== Script completado ==="
echo "Ahora edita /root/edge-sec-agent/secrets.env con tus credenciales reales."
echo "Luego prueba: /usr/local/bin/telegram-notify.sh 'Hola'"
exit 0