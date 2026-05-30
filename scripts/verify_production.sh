#!/bin/bash
# verify_production.sh – Verificación consolidada del entorno Edge Sec Agent
# Ejecutar como root.

set -euo pipefail

GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[0;33m"
RESET="\033[0m"

ROOT="/root/edge-sec-agent"
SECRETS="$ROOT/secrets.env"
REPORTS_DIR="$ROOT/reports"

print_ok() { echo -e "${GREEN}[OK]${RESET} $1"; }
print_warn() { echo -e "${YELLOW}[AVISO]${RESET} $1"; }
print_fail() { echo -e "${RED}[FALLÓ]${RESET} $1"; }

ALL_OK=true

# 1) sec-web.service
if systemctl is-active --quiet sec-web.service; then
  print_ok "sec-web.service está activo"
else
  print_fail "sec-web.service NO está activo"
  ALL_OK=false
fi

# 2) Dashboard en 8080
if curl -sS -I http://127.0.0.1:8080/ | head -n1 | grep -q "200 OK"; then
  print_ok "Dashboard en 8080 responde (HTTP 200)"
else
  print_warn "Dashboard 8080 no responde o no devuelve 200"
  ALL_OK=false
fi

# 3) sec-agent --security --json
if command -v sec-agent >/dev/null 2>&1; then
  JSON_OUT=$(sec-agent --security --json 2>&1 || true)
  if command -v jq >/dev/null 2>&1; then
    if echo "$JSON_OUT" | jq -e . >/dev/null 2>&1; then
      SCORE=$(echo "$JSON_OUT" | jq -r '.score // empty')
      print_ok "sec-agent --security --json devuelve JSON válido. Score=${SCORE:-0}"
    else
      print_fail "sec-agent --security --json no es JSON válido"
      ALL_OK=false
    fi
  else
    print_warn "jq no disponible; no se puede validar JSON" 
  fi
else
  print_warn "sec-agent no encontrado"
  ALL_OK=false
fi

# 4) secrets.env
if [ -f "$SECRETS" ]; then
  print_ok "Secrets env existente: $SECRETS"
else
  print_warn "Secrets env NO encontrado"
  ALL_OK=false
fi

# 5) sec-report.timer
if systemctl is-active --quiet sec-report.timer; then
  print_ok "sec-report.timer está activo"
else
  print_warn "sec-report.timer no está activo"
  ALL_OK=false
fi

# 6) Directorio de reportes
if [ -d "$REPORTS_DIR" ]; then
  print_ok "Directorio de reportes existente: $REPORTS_DIR"
else
  print_warn "Directorio de reportes no existente"
  ALL_OK=false
fi

# 7) MCP log-analyzer (ejemplo)
if [ -x "$ROOT/mcp_tools/log-analyzer" ]; then
  print_ok "MCP log-analyzer existente y ejecutable"
else
  print_warn "MCP log-analyzer no encontrado o no ejecutable"
  ALL_OK=false
fi

# 8) Health endpoint del proxy (ruta correcta)
URL_PROXY="http://127.0.0.1:8765/v1/global/health"
if curl -sSf "$URL_PROXY" >/dev/null 2>&1; then
  print_ok "Proxy OpenAI health endpoint disponible"
else
  print_warn "Proxy OpenAI health endpoint no disponible"
  ALL_OK=false
fi

# Resumen final
if [ "$ALL_OK" = true ]; then
  echo -e "\n${GREEN}ENTORNO LISTO PARA PRODUCCIÓN${RESET}"
else
  echo -e "\n${RED}ALGUNOS COMPONENTES REQUIEREN ATENCIÓN${RESET}"
fi
