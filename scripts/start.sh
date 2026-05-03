#!/usr/bin/env bash
# Edge Sec Agent — inicio limpio
# Reinicia Ollama, espera que cargue y lanza el agente
# Uso: ./scripts/start.sh [argumentos del agente]

set -euo pipefail

AGENT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
AGENT="$AGENT_DIR/src/agent.py"
WAIT=20

echo "🔄 Reiniciando Ollama..."
systemctl restart ollama

echo "⏳ Esperando ${WAIT}s para que Ollama cargue..."
sleep "$WAIT"

echo "🟢 Verificando Ollama..."
if ! curl -sf http://localhost:11434/api/tags > /dev/null; then
    echo "❌ Ollama no responde. Revisa: journalctl -fu ollama"
    exit 1
fi

echo "✅ Ollama listo"
echo ""

exec python3 "$AGENT" "$@"