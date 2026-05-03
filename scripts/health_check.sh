#!/usr/bin/env bash
# Edge Sec Agent — health check
# Verifica el estado de todos los componentes del proyecto

PASS=0
FAIL=0

check() {
    local name="$1"
    local cmd="$2"
    if eval "$cmd" > /dev/null 2>&1; then
        echo "  ✅ $name"
        ((PASS++)) || true
    else
        echo "  ❌ $name"
        ((FAIL++)) || true
    fi
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🦞 Edge Sec Agent — Health Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "🖥️  Sistema:"
check "Python 3.11+" "python3 --version | grep -E '3\.(1[1-9]|[2-9][0-9])'"
check "Git instalado" "git --version"
check "curl instalado" "curl --version"
echo ""

echo "🤖 Ollama:"
check "Servicio activo" "systemctl is-active --quiet ollama"
check "API responde" "curl -sf http://localhost:11434/api/tags"
check "TinyLlama presente" "curl -sf http://localhost:11434/api/tags | grep -q tinyllama"
echo ""

echo "📁 Proyecto:"
AGENT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
check "src/agent.py existe" "test -f $AGENT_DIR/src/agent.py"
check "agent.py usa urllib" "grep -q 'urllib.request' $AGENT_DIR/src/agent.py"
check "docs/SETUP.md existe" "test -f $AGENT_DIR/docs/SETUP.md"
check "Git repo OK" "git -C $AGENT_DIR status"
echo ""

echo "💾 Recursos:"
RAM_MB=$(free -m | awk '/Mem/{print $7}')
DISK_PCT=$(df / | awk 'NR==2{print $5}' | tr -d '%')

if [ "$RAM_MB" -gt 500 ]; then
    echo "  ✅ RAM libre: ${RAM_MB} MB"
    ((PASS++)) || true
else
    echo "  ⚠️  RAM libre: ${RAM_MB} MB (puede ser insuficiente)"
    ((FAIL++)) || true
fi

if [ "$DISK_PCT" -lt 85 ]; then
    echo "  ✅ Disco /: ${DISK_PCT}% usado"
    ((PASS++)) || true
else
    echo "  ⚠️  Disco /: ${DISK_PCT}% usado (casi lleno)"
    ((FAIL++)) || true
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Resultado: ✅ $PASS OK  |  ❌ $FAIL FAIL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

[ "$FAIL" -eq 0 ] && exit 0 || exit 1