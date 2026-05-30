#!/bin/bash
GREEN="\033[0;32m"; RED="\033[0;31m"; YELLOW="\033[0;33m"; NC="\033[0m"
echo "=== Health Check Edge Sec Agent ==="
systemctl is-active sec-proxy sec-report.timer >/dev/null && echo -e "${GREEN}✅ Servicios críticos activos${NC}" || echo -e "${RED}❌ Algun servicio crítico caído${NC}"
if command -v jq >/dev/null; then
    SCORE=$(sec-agent --security --json 2>/dev/null | jq -r '.score // "N/A"')
    echo "Puntuación actual: $SCORE"
fi
curl -sS http://localhost:5000/v1/global/health >/dev/null && echo -e "${GREEN}✅ API REST responde${NC}" || echo -e "${RED}❌ API REST no responde${NC}"
curl -sS http://localhost:8080 >/dev/null && echo -e "${GREEN}✅ Dashboard web responde${NC}" || echo -e "${YELLOW}⚠️ Dashboard no accesible${NC}"
echo "Fecha: $(date)"
