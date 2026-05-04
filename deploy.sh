#!/bin/bash
# deploy_edge_sec_agent_one_shot.sh
# Despliegue automatizado y seguro para "edge-sec-agent" en una Orange Pi Zero 3 (Debian)
# - Sobrescribe wrapper sec-agent con detección robusta de --security/--json (regEx Bash)
# - Parchea agent.py main() para manejo correcto de --json
# - Crea telegram-notify.sh (con jq, timeout y envío de docs para mensajes largos)
# - Crea report-cron.sh (ejecuta sec-agent --security --json, parsea con jq, envía Telegram y correo)
# - Crea telegram.conf con placeholders
# - Realiza backups idempotentes de archivos relevantes
# - Genera prueba final JSON
# - Este script es idempotente y seguro (backups con timestamp)

set -euo pipefail

ROOT="/root/edge-sec-agent"
BACKUP_DIR="$ROOT/backups"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

# Archivos a respaldar/editar
WRAPPER="/usr/local/bin/sec-agent"
AGENT_PY="/root/edge-sec-agent/src/agent.py"
TELE_NOTIFY="/usr/local/bin/telegram-notify.sh"
REPORT_CRON="/usr/local/bin/report-cron.sh"
TELE_CONF="/etc/edge-sec-agent/telegram.conf"

# 1) Respaldos (idempotentes)
mkdir -p "$BACKUP_DIR"
backup_if_exists() {
  local f="$1"
  if [ -e "$f" ]; then
    cp -p "$f" "$BACKUP_DIR/$(basename "$f").${TIMESTAMP}.bak"
    echo "[BACKUP] $f -> ${BACKUP_DIR}/$(basename "$f").${TIMESTAMP}.bak"
  else
    echo "[INFO] No existe $f para respaldar."
  fi
}

backup_if_exists "$WRAPPER"
backup_if_exists "$AGENT_PY"
backup_if_exists "$TELE_NOTIFY"
backup_if_exists "$REPORT_CRON"

# 2) Sobrescribir /usr/local/bin/sec-agent con wrapper robusto
sudo /bin/bash -lc "cat > \"$WRAPPER\" <<'EOF'\n#!/bin/bash\n# sec-agent\n# Wrapper robusto que pasa todos los argumentos a Python cuando se detecta --security o --json,\n# y deriva a sec/ia cuando no se usan esas banderas.\nset -euo pipefail\n\n# Ruta absoluta al script Python del agente\nAGENT_PY=\"/root/edge-sec-agent/src/agent.py\"\n\nPREGUNTA=\"$*\"\n\nif [ -z \"$PREGUNTA\" ]; then\n  echo \"Uso: sec-agent 'consulta'\"\n  exit 1\nfi\n\n# Detección robusta de --security o --json en cualquier posición usando Bash regex\nif [[ \"$PREGUNTA\" =~ (^|[[:space:]])(--security|--json)([[:space:]]|$) ]]; then\n  python3 \"$AGENT_PY\" \"$@\"\n  exit 0\nfi\n\nLOW=$(echo \"$PREGUNTA\" | tr '[:upper:]' '[:lower:]')\n\nif [[ \"$LOW\" =~ (^|[[:space:]])(red|dispositivos|arp|arp -a)([[:space:]]|$) ]]; then\n  /usr/local/bin/sec red\n  exit 0\nelif [[ \"$LOW\" =~ (^|[[:space:]])(puertos|ports)([[:space:]]|$) ]]; then\n  /usr/local/bin/sec puertos\n  exit 0\nelif [[ \"$LOW\" =~ (^|[[:space:]])(ram|memoria)([[:space:]]|$) ]]; then\n  /usr/local/bin/sec ram\n  exit 0\nelif [[ \"$LOW\" =~ (^|[[:space:]])(temp|temperatura)([[:space:]]|$) ]]; then\n  /usr/local/bin/sec temp\n  exit 0\nelif [[ \"$LOW\" =~ (^|[[:space:]])(status|estado|kernel|logs|servicio|reiniciar|firewall|fail2ban|docker|actualizar|update)([[:space:]]|$) ]]; then\n  /usr/local/bin/sec status\n  exit 0\nelse\n  python3 \"$AGENT_PY\" \"$@\"\n  exit 0\nfi\nEOF"

chmod +x "$WRAPPER"
echo "[OK] sec-agent wrapper instalado/actualizado en $WRAPPER"

# 3) Patch básico de main() en src/agent.py para soporte --json junto a --security
# Solo añade el fragmento si no está presente.
python3 - << 'PY'
import io,sys
from pathlib import Path

p = Path("/root/edge-sec-agent/src/agent.py")
if not p.exists():
    print("[WARN] No se encontró /root/edge-sec-agent/src/agent.py; saltando patch.")
    sys.exit(0)

text = p.read_text(encoding="utf-8")
if "--json\" in args" in text or "\"--json\" in args" in text:
    print("[INFO] main() ya contiene manejo de --json.")
else:
    old = "    args = sys.argv[1:]"
    if old in text:
        patch = (
            old + "\n\n"
            "    # Soporte de --json y --security\n"
            "    json_output = \"--json\" in args\n\n"
            "    # Procesar seguridad si existe\n"
            "    if \"--security\" in args:\n"
            "        cmd_security(json_output=json_output)\n"
            "        return\n"
        )
        text = text.replace(old, patch)
        p.write_text(text, encoding="utf-8")
        print("[OK] Patched main() para manejar --json (--security).")
    else:
        print("[WARN] No se encontró la línea esperada para patch. No se aplicó.")
PY

# 4) Crear /usr/local/bin/telegram-notify.sh con código mejorado
sudo tee "$TELE_NOTIFY" > /dev/null <<'EOF'
#!/bin/bash
# telegram-notify.sh
# Envia mensajes a Telegram usando la API Bot API, leyendo token y chat desde /etc/edge-sec-agent/telegram.conf
set -euo pipefail

CONFIG="/etc/edge-sec-agent/telegram.conf"

# Cargar configuración
if [ -f "$CONFIG" ]; then
  # shellcheck disable=SC1090
  . "$CONFIG"
fi

TOKEN="${TELEGRAM_BOT_TOKEN:-}"
CHAT_ID="${TELEGRAM_CHAT_ID:-}"

if [ -z "$TOKEN" ] || [ -z "$CHAT_ID" ]; then
  echo "ERROR: TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no definidos en $CONFIG" >&2
  exit 1
fi

# Mensaje a enviar (usar todos los argumentos como un único texto)
MESSAGE="$*"
if [ -z "$MESSAGE" ]; then
  echo "ERROR: Debes proporcionar el texto del mensaje como argumento." >&2
  exit 1
fi

MAX_LEN=4096

# Detectar si el mensaje es JSON (utilizando jq si está disponible)
is_json=0
if command -v jq >/dev/null 2>&1; then
  if echo "$MESSAGE" | jq -e . >/dev/null 2>&1; then
    is_json=1
  fi
fi

send_text() {
  local text="$1"
  curl -sS --max-time 10 -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
       -d chat_id="${CHAT_ID}" \
       --data-urlencode "text=${text}" >/dev/null 2>&1 || {
        echo "[WARN] Telegram sendMessage failed" >&2
        return 1
      }
}

send_document() {
  local file="$1"
  curl -sS --max-time 10 -X POST "https://api.telegram.org/bot${TOKEN}/sendDocument" \
       -F "chat_id=${CHAT_ID}" \
       -F "document=@${file};filename=document.txt" \
       -F "caption=Full security report attached" \
       >/dev/null 2>&1 || {
        echo "[WARN] Telegram sendDocument failed" >&2
        return 1
      }
}

TEXT=""
if [ "$is_json" -eq 1 ]; then
  if command -v jq >/dev/null 2>&1; then
    SCORE=$(echo "$MESSAGE" | jq -r '.score // empty')
    SSH_FAILS=$(echo "$MESSAGE" | jq -r '.ssh_failures // empty')
    OPEN_PORTS=$(echo "$MESSAGE" | jq -r '.open_ports | if type=="array" then join(",") else "" end' 2>/dev/null)
    TEMP_C=$(echo "$MESSAGE" | jq -r '.temp_c // empty')
    RAM_P=$(echo "$MESSAGE" | jq -r '.ram_percent // empty')
    TEXT=$(printf "Informe de Seguridad\nScore: %s\nSSH fallos: %s\nPuertos: %s\nTemp CPU: %sC\nRAM: %s%%" \
      "${SCORE:-0}" "${SSH_FAILS:-0}" "${OPEN_PORTS:-}" "${TEMP_C:-}" "${RAM_P:-0}")
  else
    # Fallback básico (no jq)
    SCORE=$(echo "$MESSAGE" | grep -oE '"score"\s*:\s*[0-9]+' | head -n1 | awk -F: '{print $2}' | tr -d ' ')
    SSH_FAILS=$(echo "$MESSAGE" | grep -oE '"ssh_failures"\s*:\s*[0-9]+' | head -n1 | awk -F: '{print $2}' | tr -d ' ')
    OPEN_PORTS_JSON=$(echo "$MESSAGE" | grep -oE '"open_ports"\s*:\s*\[[^]]*\]' | head -n1)
    OPEN_PORTS=""
    if [ -n "$OPEN_PORTS_JSON" ]; then
      inner=$(echo "$OPEN_PORTS_JSON" | sed -E 's/.*\[(.*)\].*/\1/')
      inner=$(echo "$inner" | tr -d '"')
      ports_list=$(echo "$inner" | tr ',' ' ' | tr -s ' ')
      OPEN_PORTS=$(echo "$ports_list" | tr ' ' ',')
    fi
    TEMP_C=$(echo "$MESSAGE" | grep -oE '"temp_c"\s*:\s*[-0-9.]+' | head -n1 | awk -F: '{print $2}' | tr -d ' ')
    RAM_P=$(echo "$MESSAGE" | grep -oE '"ram_percent"\s*:\s*[-0-9.]+' | head -n1 | awk -F: '{print $2}' | tr -d ' ')
    TEXT=$(printf "Informe de Seguridad\nScore: %s\nSSH fallos: %s\nPuertos: %s\nTemp CPU: %sC\nRAM: %s%%" \
      "${SCORE:-0}" "${SSH_FAILS:-0}" "${OPEN_PORTS:-}" "${TEMP_C:-}" "${RAM_P:-0}")
  fi
else
  TEXT="$MESSAGE"
fi

if [ ${#TEXT} -le $MAX_LEN ]; then
  send_text "$TEXT"
else
  TMP="$(mktemp)"
  printf "%s" "$TEXT" > "$TMP"
  send_document "$TMP"
  rm -f "$TMP"
fi

exit 0
EOF
chmod +x "$TELE_NOTIFY"

# 5) Crear /usr/local/bin/report-cron.sh
sudo tee "$REPORT_CRON" > /dev/null <<'EOF'
#!/bin/bash
# report-cron.sh
# Ejecuta sec-agent --security --json, envía alerta por Telegram y correo
set -euo pipefail

AGENT="/usr/local/bin/sec-agent"
LOG="/var/log/edge-sec-report.log"

# Cargar configuración de correo y Telegram
ENV_FILES=(
  "/etc/edge-sec-agent/sec-report.env"
  "/etc/default/edge-sec-agent"
)
for f in "${ENV_FILES[@]}"; do
  if [ -f "$f" ]; then
    . "$f" >/dev/null 2>&1 || true
  fi
done

# Cargar configuración de Telegram si existe
if [ -f "/etc/edge-sec-agent/telegram.conf" ]; then
  # shellcheck disable=SC1090
  . "/etc/edge-sec-agent/telegram.conf" || true
fi

# Enviar notificaciones por Telegram (si disponible)
TELEGRAM_NOTIFY="/usr/local/bin/telegram-notify.sh"

# Ejecutar reporte
if [ ! -x "$AGENT" ]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') - ERROR: sec-agent no encontrado" | tee -a "$LOG" >&2
  exit 1
fi

OUTPUT="$("$AGENT" --security --json 2>&1)"
RC=$?

# Parse JSON con jq si está disponible
if command -v jq >/dev/null 2>&1; then
  SCORE=$(echo "$OUTPUT" | jq -r '.score // empty')
  SSH_FAILS=$(echo "$OUTPUT" | jq -r '.ssh_failures // empty')
  OPEN_PORTS=$(echo "$OUTPUT" | jq -r '.open_ports | if type=="array" then join(",") else "" end')
  TEMP_C=$(echo "$OUTPUT" | jq -r '.temp_c // empty')
  RAM_P=$(echo "$OUTPUT" | jq -r '.ram_percent // empty')
  REPORT_PATH=$(echo "$OUTPUT" | jq -r '.report_path // empty')
else
  SCORE=$(echo "$OUTPUT" | grep -oE '"score"\s*:\s*[0-9]+' | head -n1 | awk -F: '{print $2}' | tr -d ' ')
  SSH_FAILS=$(echo "$OUTPUT" | grep -oE '"ssh_failures"\s*:\s*[0-9]+' | head -n1 | awk -F: '{print $2}' | tr -d ' ')
  OPEN_PORTS_JSON=$(echo "$OUTPUT" | grep -oE '"open_ports"\s*:\s*\[[^]]*\]' | head -n1)
  OPEN_PORTS=""
  if [ -n "$OPEN_PORTS_JSON" ]; then
    inner=$(echo "$OPEN_PORTS_JSON" | sed -E 's/.*\[(.*)\].*/\1/')
    inner=$(echo "$inner" | tr -d '"')
    ports_list=$(echo "$inner" | tr ',' ' ' | tr -s ' ')
    OPEN_PORTS=$(echo "$ports_list" | tr ' ' ',')
  fi
  TEMP_C=$(echo "$OUTPUT" | grep -oE '"temp_c"\s*:\s*[-0-9.]+' | head -n1 | awk -F: '{print $2}' | tr -d ' ')
  RAM_P=$(echo "$OUTPUT" | grep -oE '"ram_percent"\s*:\s*[-0-9.]+' | head -n1 | awk -F: '{print $2}' | tr -d ' ')
fi

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
REPORT_PATH="${REPORT_PATH:-}"

if [ -n "$REPORT_PATH" ] && [ "$REPORT_PATH" != "null" ]; then
  echo "$TIMESTAMP - SUCCESS - $REPORT_PATH" >> "$LOG"
else
  echo "$TIMESTAMP - JSON_ONLY_OR_NO_SAVE - Score: ${SCORE:-0}" >> "$LOG"
fi

# Telegram: enviar siempre si SEND_FULL_REPORT=yes o enviar según score
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
  if [ "${SEND_FULL_REPORT:-no}" = "yes" ] || [ -f /etc/edge-sec-agent/send_full_report ]; then
    /usr/local/bin/telegram-notify.sh "$OUTPUT" || true
  elif [ -n "${SCORE:-}" ] && [ "${SCORE:-0}" -lt 70 ]; then
    SHORT="Alerta Edge Sec Agent: puntuación ${SCORE:-0}/100. SSH fallos: ${SSH_FAILS:-0}; Puertos: ${OPEN_PORTS:-}; Temp: ${TEMP_C}C; RAM: ${RAM_P:-0}%."
    /usr/local/bin/telegram-notify.sh "$SHORT" || true
  fi
fi

# Enviar correo si ALERT_EMAIL está configurado
if [ -n "${ALERT_EMAIL:-}" ]; then
  MAIL_BODY="$OUTPUT"
  if command -v mailx >/dev/null 2>&1; then
    printf "%s" "$MAIL_BODY" | mailx -s "Edge Sec Agent Security Report" "$ALERT_EMAIL" || {
      echo "$(date '+%Y-%m-%d %H:%M:%S') - WARN: fallo enviando correo con mailx" >> "$LOG"
    }
  elif command -v mail >/dev/null 2>&1; then
    printf "%s" "$MAIL_BODY" | mail -s "Edge Sec Agent Security Report" "$ALERT_EMAIL" || {
      echo "$(date '+%Y-%m-%d %H:%M:%S') - WARN: fallo enviando correo con mail" >> "$LOG"
    }
  elif command -v sendmail >/dev/null 2>&1; then
    printf "Subject: Edge Sec Agent Security Report\nTo: %s\n\n%s" "$ALERT_EMAIL" "$MAIL_BODY" | sendmail -t || {
      echo "$(date '+%Y-%m-%d %H:%M:%S') - WARN: fallo enviando correo con sendmail" >> "$LOG"
    }
  else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - WARN: No mail utility found (mailx, mail, sendmail). No email sent." >> "$LOG"
  fi
fi

exit 0
EOF
chmod +x "$REPORT_CRON"

# 6) Telegram.conf de ejemplo (placeholders)
sudo mkdir -p /etc/edge-sec-agent
sudo tee "$TELE_CONF" > /dev/null << 'CONF'
TELEGRAM_BOT_TOKEN="your-bot-token-here"
TELEGRAM_CHAT_ID="your-chat-id-here"
SEND_FULL_REPORT=yes
CONF
echo "[OK] telegram.conf creado en /etc/edge-sec-agent/telegram.conf (placeholders)."

# 7) Permisos de ejecución
chmod +x "$WRAPPER" "$TELE_NOTIFY" "$REPORT_CRON"

# 8) Prueba final
echo -e "\n[TEST] Verificación rápida del JSON generado por sec-agent --security --json"
if command -v jq >/dev/null 2>&1; then
  sec-agent --security --json | jq . 2>/dev/null || echo "El resultado no es JSON válido o jq no puede parsearlo."
else
  echo "jq no está disponible. Ejecuta: sec-agent --security --json | head -n 20"
  sec-agent --security --json
fi

echo -e "\n[INSTRUCCIONES] Edita $TELE_CONF con tus credenciales reales (TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID)."
echo "Luego prueba el envío manualmente con:"
echo "  /usr/local/bin/telegram-notify.sh 'Mensaje de prueba del sistema'"
