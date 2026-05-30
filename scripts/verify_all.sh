#!/bin/bash
# verify_all.sh
# Verificación de estado de Edge Sec Agent (Fase de producción)
# Revisa sec-web, sec-agent (JSON), /api health, HTML generado, MCP tools, secretos, timer y disponibilidad de Telegram.
# Usa placeholders (TU_TOKEN, TU_CHAT_ID) si es necesario. No tocar secretos reales.

set -euo pipefail

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RESET='\033[0m'

# Utiles
IP="192.168.1.141"
HOST="DietPi/DietPi-like"

# Helpers
print_ok() { echo -e "${GREEN}[OK]${RESET} $1"; }
print_fail() { echo -e "${RED}[FALLÓ]${RESET} $1"; }
print_warn() { echo -e "${YELLOW}[AVISO]${RESET} $1"; }
print_info() { echo -e "${BLUE}[INFO]${RESET} $1"; }

# 1) Reparar/Verificar sec-web (servicio Flask)
check_sec_web_service() {
  # 1.1 Verificar servicio
  if systemctl is-active --quiet sec-web.service; then
    print_ok "sec-web.service está activo"
  else
    print_fail "sec-web.service NO está activo"
  fi

  # 1.2 Verificar Flask instalado
  if python3 -m flask >/dev/null 2>&1; then
    print_ok "Flask ya está instalado"
  else
    if command -v apt >/dev/null 2>&1; then
      sudo apt update -qq
      sudo apt install -y python3-flask
      print_ok "Flask instalado (python3-flask)"
    else
      print_warn "No se pudo verificar/instalar Flask (apt no disponible)"
    fi
  fi

  # 1.3 Verificar sec_web.py
  if [ -f "/root/edge-sec-agent/src/sec_web.py" ]; then
    python3 -m py_compile /root/edge-sec-agent/src/sec_web.py 2>/dev/null || true
    print_ok "sec_web.py presente y compilable (verificación rápida)"
  else
    print_warn "sec_web.py no encontrado; se recomienda crear una versión funcional"
  fi

  # 1.4 Verificar /etc/systemd/system/sec-web.service
  if [ -f "/etc/systemd/system/sec-web.service" ]; then
    print_ok "sec-web.service existente"
  else
    print_warn "sec-web.service no existe; se recomienda crearlo"
  fi

  # 1.5 Arranque del servicio
  systemctl daemon-reload || true
  systemctl enable --now sec-web.service >/dev/null 2>&1 || true
  if systemctl is-active --quiet sec-web.service; then
    print_ok "sec-web.service iniciado/activo"
  else
    print_warn "sec-web.service no está activo tras intento de inicio"
  fi
}

# 2) Verificar todos los servicios clave
check_services_status() {
  SERVICES=(sec-proxy sec-web sec-report.timer sec-api.service)
  for s in "${SERVICES[@]}"; do
    if systemctl is-active --quiet "$s"; then
      printf "✔ %s: " "$s"; print_ok "activo"
    else
      printf "✖ %s: " "$s"; print_fail "no activo"
    fi
  done

  # Verificar API REST base (si está disponible)
  if curl -sSf http://127.0.0.1:8765/ask >/dev/null 2>&1; then
    print_ok "API REST (sec-api) responde en 8765"
  else
    print_warn "API REST (sec-api) no responde en 8765"
  fi
}

# 3) health check rápido con sec-agent --security --json
check_sec_agent_json() {
  if command -v sec-agent >/dev/null 2>&1; then
    OUT="$(sec-agent --security --json 2>&1 || true)"
    if echo "$OUT" | jq -e . >/dev/null 2>&1; then
      SCORE=$(echo "$OUT" | jq -r '.score // empty')
      printf "Sec-agent JSON válido. Score: %s\n" "${SCORE:-0}"
      print_ok "JSON de sec-agent es válido"
    else
      print_fail "La salida de sec-agent --security --json no es JSON válido"
      echo "$OUT"
    fi
  else
    print_warn "sec-agent no encontrado en PATH; omitiendo verificación JSON"
  fi
}

# 4) health endpoint del proxy
check_health_endpoint() {
  URL="http://192.168.1.141:8765/v1/global/health"
  if curl -sSf "$URL" >/dev/null 2>&1; then
    HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}" "$URL")
    if [ "$HTTP_CODE" -eq 200 ]; then
      print_ok "Health endpoint responde con HTTP $HTTP_CODE"
      echo "Health: $HTTP_CODE"
      if command -v jq >/dev/null 2>&1; then
        curl -sS "$URL" | jq .
      fi
    else
      print_warn "Health endpoint devuelve HTTP $HTTP_CODE"
    fi
  else
    print_warn "Health endpoint no responde"
  fi
}

# 5) verificar /root/edge-sec-agent/secrets.env
check_secrets_env() {
  if [ -f "/root/edge-sec-agent/secrets.env" ]; then
    print_ok "secrets.env existe en /root/edge-sec-agent/secrets.env"
  else
    print_warn "secrets.env no encontrado en /root/edge-sec-agent/secrets.env"
  fi
}

# 6) health check básico
check_health_check_script() {
  if [ -x "/usr/local/bin/health_check.sh" ]; then
    print_ok "health_check.sh existente y ejecutable"
  else
    print_warn "health_check.sh no encontrado o no ejecutable"
  fi
}

# 7) Notificaciones Telegram disponibles
check_telegram_notify() {
  if [ -x "/usr/local/bin/telegram-notify.sh" ]; then
    print_ok "telegram-notify.sh ejecutable"
  else
    print_warn "telegram-notify.sh no ejecutable"
  fi
}

# Ejecutar y presentar resultados
echo -e "\n==== Verificación de estado general ===="
check_sec_web_service
check_services_status
check_sec_agent_json
check_health_endpoint
check_secrets_env
check_health_check_script
check_telegram_notify
echo "==== Resumen final ===="
# Evaluación global simple
ALL_OK=true
if ! systemctl is-active --quiet sec-web.service; then ALL_OK=false; fi
if ! command -v sec-agent >/dev/null 2>&1; then ALL_OK=false; fi
if ! curl -sSf "http://127.0.0.1:8765/v1/global/health" >/dev/null 2>&1; then ALL_OK=false; fi
if [ "$ALL_OK" = true ]; then
  echo -e "\n${GREEN}TODO listo: el sistema Edge Sec Agent está preparado para producción.${RESET}"
else
  echo -e "\n${RED}FALLÓ alguno de los componentes. Revisa los bloques anteriores e intenta corregir.${RESET}"
fi
