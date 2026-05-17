#!/bin/bash
set -euo pipefail

###############################################################################
# security_audit.sh — Auditoría Automatizada de Seguridad Perimetral
# Edge Security Agent — Orange Pi Zero 3
#
# Propósito: Verificar en un solo paso que todas las capas de defensa están
# operativas: firewall iptables, aislamiento SSH, aislamiento de backend
# Gunicorn, proxy inverso Nginx y endpoint de health check.
#
# Uso: bash scripts/security_audit.sh
# Salida: [OK] en verde para comprobaciones superadas
#         [FAIL] en rojo para comprobaciones fallidas
###############################################################################

# Colores ANSI para salida en terminal
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m' # No Color

PASS=0
FAIL=0
TOTAL=0

# Función auxiliar: imprimir resultado
print_result() {
    local label="$1"
    local status="$2"  # "pass" o "fail"
    local detail="$3"
    TOTAL=$((TOTAL + 1))

    if [ "$status" = "pass" ]; then
        PASS=$((PASS + 1))
        echo -e "  ${GREEN}[OK]${NC}   ${label}"
        [ -n "$detail" ] && echo -e "        ${detail}"
    else
        FAIL=$((FAIL + 1))
        echo -e "  ${RED}[FAIL]${NC} ${label}"
        [ -n "$detail" ] && echo -e "        ${RED}${detail}${NC}"
    fi
}

# Cabecera
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   Edge Security Agent — Auditoría de Seguridad          ║${NC}"
echo -e "${BOLD}║   Orange Pi Zero 3 | $(date '+%Y-%m-%d %H:%M:%S')                  ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

###############################################################################
# 1. VERIFICACIÓN DE FIREWALL — Regla DROP en puerto 22
###############################################################################
echo -e "${BOLD}[1/5] Firewall: Regla DROP en puerto 22${NC}"

if iptables -L INPUT -n 2>/dev/null | grep -q "dpt:22.*DROP"; then
    print_result "Regla DROP puerto 22 (IPv4)" "pass" "$(iptables -L INPUT -n | grep 'dpt:22.*DROP')"
else
    print_result "Regla DROP puerto 22 (IPv4)" "fail" "No se encontró regla DROP para dport 22 en iptables"
fi

if ip6tables -L INPUT -n 2>/dev/null | grep -q "dpt:22.*DROP"; then
    print_result "Regla DROP puerto 22 (IPv6)" "pass" "$(ip6tables -L INPUT -n | grep 'dpt:22.*DROP')"
else
    print_result "Regla DROP puerto 22 (IPv6)" "fail" "No se encontró regla DROP para dport 22 en ip6tables"
fi

echo ""

###############################################################################
# 2. VERIFICACIÓN DE SSH ALTERNATIVO — Dropbear en puerto 2222
###############################################################################
echo -e "${BOLD}[2/5] SSH Alternativo: Dropbear en puerto 2222${NC}"

if ss -tlnp 2>/dev/null | grep -q ":2222\b"; then
    LISTEN_ADDR=$(ss -tlnp | grep ":2222" | head -1)
    print_result "Dropbear escuchando en puerto 2222" "pass" "$LISTEN_ADDR"
else
    print_result "Dropbear escuchando en puerto 2222" "fail" "No hay ningún servicio escuchando en el puerto 2222"
fi

# Verificación adicional: confirmar que NO hay nada en puerto 22
if ss -tlnp 2>/dev/null | grep -q ":22\b" | grep -v ":2222"; then
    print_result "Puerto 22 cerrado (sin servicio)" "fail" "Algo sigue escuchando en puerto 22 — posible brecha de seguridad"
else
    print_result "Puerto 22 cerrado (sin servicio)" "pass" "Ningún servicio activo en puerto 22"
fi

echo ""

###############################################################################
# 3. VERIFICACIÓN DE AISLAMIENTO DE BACKEND — Gunicorn en 127.0.0.1:5000
###############################################################################
echo -e "${BOLD}[3/5] Aislamiento de Backend: Gunicorn en 127.0.0.1:5000${NC}"

if ss -tlnp 2>/dev/null | grep -q "127.0.0.1:5000"; then
    print_result "Gunicorn en 127.0.0.1:5000 (loopback)" "pass" "$(ss -tlnp | grep '127.0.0.1:5000')"
else
    print_result "Gunicorn en 127.0.0.1:5000 (loopback)" "fail" "Gunicorn no está escuchando en 127.0.0.1:5000"
fi

# Verificación crítica: confirmar que NO escucha en 0.0.0.0:5000
if ss -tlnp 2>/dev/null | grep -q "0.0.0.0:5000"; then
    print_result "Gunicorn NO expuesto a 0.0.0.0" "fail" "CRÍTICO: Gunicorn expuesto a todas las interfaces de red"
else
    print_result "Gunicorn NO expuesto a 0.0.0.0" "pass" "Backend aislado correctamente — inaccesible desde red externa"
fi

echo ""

###############################################################################
# 4. VERIFICACIÓN DE PROXY INVERSO — Nginx activo en puerto 8080
###############################################################################
echo -e "${BOLD}[4/5] Proxy Inverso: Nginx en puerto 8080${NC}"

if ss -tlnp 2>/dev/null | grep -q ":8080\b"; then
    print_result "Nginx escuchando en puerto 8080" "pass" "$(ss -tlnp | grep ':8080')"
else
    print_result "Nginx escuchando en puerto 8080" "fail" "Nginx no está escuchando en el puerto 8080"
fi

if systemctl is-active --quiet nginx 2>/dev/null; then
    print_result "Servicio Nginx activo (systemd)" "pass" "Estado: active (running)"
else
    print_result "Servicio Nginx activo (systemd)" "fail" "El servicio nginx no está activo en systemd"
fi

echo ""

###############################################################################
# 5. SIMULACIÓN INTERNA DE HEALTH CHECK — Endpoint /v1/global/health
###############################################################################
echo -e "${BOLD}[5/5] Health Check: Endpoint /v1/global/health${NC}"

HTTP_CODE=$(curl -s -o /tmp/health_response.json -w "%{http_code}" http://127.0.0.1:8080/v1/global/health 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
    print_result "HTTP 200 OK" "pass" "Código de respuesta: $HTTP_CODE"
else
    print_result "HTTP 200 OK" "fail" "Código de respuesta: $HTTP_CODE (esperado: 200)"
fi

HEALTH_STATUS=$(python3 -c "import json; print(json.load(open('/tmp/health_response.json')).get('status',''))" 2>/dev/null || echo "")

if [ "$HEALTH_STATUS" = "HEALTHY" ]; then
    print_result "Estado HEALTHY confirmado" "pass" "Respuesta del endpoint: $HEALTH_STATUS"
else
    print_result "Estado HEALTHY confirmado" "fail" "Estado recibido: '$HEALTH_STATUS' (esperado: HEALTHY)"
fi

# Extraer y mostrar temperatura de CPU si está disponible
CPU_TEMP=$(python3 -c "import json; t=json.load(open('/tmp/health_response.json')).get('hardware',{}).get('cpu_temp_c'); print(f'{t}°C' if t else 'N/A')" 2>/dev/null || echo "N/A")
echo -e "        ${YELLOW}Temperatura CPU: $CPU_TEMP${NC}"

# Limpiar archivo temporal
rm -f /tmp/health_response.json

echo ""

###############################################################################
# RESUMEN FINAL DE AUDITORÍA
###############################################################################
echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║                    RESULTADO FINAL                       ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Comprobaciones totales:  ${BOLD}$TOTAL${NC}"
echo -e "  Superadas:               ${GREEN}$PASS${NC}"
echo -e "  Fallidas:                ${RED}$FAIL${NC}"
echo ""

if [ "$FAIL" -eq 0 ]; then
    echo -e "  ${GREEN}${BOLD}AUDITORÍA SUPERADA — Todos los controles de seguridad están operativos.${NC}"
    echo ""
    exit 0
else
    echo -e "  ${RED}${BOLD}AUDITORÍA FALLIDA — $FAIL control(es) requieren atención inmediata.${NC}"
    echo ""
    exit 1
fi
