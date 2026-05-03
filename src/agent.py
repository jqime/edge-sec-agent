#!/usr/bin/env python3
"""
Edge Sec Agent v0.3.0
Agente SecDevOps autónomo para Orange Pi Zero 3
Modelo: TinyLlama 1.1b via Ollama
"""

import urllib.request
import json
import subprocess
import sys
import time
import os

# ── Configuración ─────────────────────────────────────────────────────────────
OLLAMA_URL   = os.getenv("EDGE_OLLAMA_URL",  "http://localhost:11434/api/generate")
OLLAMA_TAGS  = os.getenv("EDGE_OLLAMA_TAGS", "http://localhost:11434/api/tags")
MODEL        = os.getenv("EDGE_MODEL",       "tinyllama:1.1b")
MAX_TOKENS   = int(os.getenv("EDGE_MAX_TOKENS", "120"))
TIMEOUT      = int(os.getenv("EDGE_TIMEOUT",    "180"))
TEMPERATURE  = float(os.getenv("EDGE_TEMP",     "0.3"))
VERSION      = "0.3.0"

# ── Helpers del sistema ───────────────────────────────────────────────────────

def run_cmd(cmd, timeout=10):
    """Ejecuta un comando shell y devuelve stdout (o stderr si falla)."""
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, timeout=timeout
        )
        return r.stdout.strip() or r.stderr.strip() or "-"
    except subprocess.TimeoutExpired:
        return "[timeout]"
    except Exception as e:
        return f"[error: {e}]"


def get_system_context():
    """Recopila datos reales del sistema operativo."""
    raw_ip = run_cmd("hostname -I").split()
    ip = raw_ip[0] if raw_ip else "?"

    raw_temp = run_cmd(
        "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null"
    )
    try:
        cpu_temp = f"{int(raw_temp)/1000:.1f}°C"
    except Exception:
        cpu_temp = "?"

    ports = run_cmd(
        "ss -tlnp 2>/dev/null | awk 'NR>1{print $4}' "
        "| rev | cut -d: -f1 | rev | sort -n | uniq | tr '\\n' ' '"
    )

    failed = run_cmd("lastb 2>/dev/null | wc -l").strip()

    return {
        "hostname": run_cmd("hostname"),
        "ip":       ip,
        "uptime":   run_cmd("uptime -p"),
        "ram":      run_cmd("free -h | awk '/Mem/{print $3\"/\"$2}'"),
        "cpu_temp": cpu_temp,
        "load":     run_cmd("uptime | awk -F'load average:' '{print $2}'").strip(),
        "ports":    ports or "ninguno",
        "failed_logins": failed,
        "disk":     run_cmd("df -h / | awk 'NR==2{print $3\"/\"$2\" (\"$5\")\"}'"),
    }

# ── Ollama ────────────────────────────────────────────────────────────────────

def check_ollama():
    """Devuelve (True, [modelos]) o (False, motivo)."""
    try:
        req = urllib.request.Request(OLLAMA_TAGS)
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            models = [m["name"] for m in data.get("models", [])]
            return True, models
    except Exception as e:
        return False, str(e)


def ask_ollama(prompt):
    """
    Envía `prompt` a Ollama con streaming y muestra tokens en tiempo real.
    Devuelve la respuesta completa como string.
    """
    payload = json.dumps({
        "model":   MODEL,
        "prompt":  prompt,
        "stream":  True,
        "options": {
            "num_predict": MAX_TOKENS,
            "temperature": TEMPERATURE,
        }
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    result = ""
    print("🤖 ", end="", flush=True)

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            for raw_line in response:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                token = chunk.get("response", "")
                print(token, end="", flush=True)
                result += token
                if chunk.get("done"):
                    break
    except urllib.error.URLError as e:
        print(f"\n❌ Error de conexión: {e.reason}")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")

    print()
    return result

# ── Modos de operación ────────────────────────────────────────────────────────

def build_context_prompt(ctx, pregunta):
    return (
        "Eres un experto SecDevOps. Analiza los datos REALES del sistema y responde en español.\n\n"
        f"SISTEMA: {ctx['hostname']} | IP: {ctx['ip']}\n"
        f"UPTIME: {ctx['uptime']} | CARGA: {ctx['load']}\n"
        f"RAM: {ctx['ram']} | CPU: {ctx['cpu_temp']} | DISCO: {ctx['disk']}\n"
        f"PUERTOS ABIERTOS: {ctx['ports']}\n"
        f"INTENTOS LOGIN FALLIDOS: {ctx['failed_logins']}\n\n"
        f"PREGUNTA: {pregunta}\n\n"
        "Responde basándote solo en los datos anteriores, máximo 4 líneas:"
    )


def cmd_security(ctx):
    """Análisis de seguridad automático."""
    print("🔍 Análisis de seguridad...\n")
    prompt = (
        "Eres un experto en ciberseguridad. Analiza estos datos REALES y responde en español.\n\n"
        f"HOST: {ctx['hostname']} | IP: {ctx['ip']}\n"
        f"RAM: {ctx['ram']} | TEMP CPU: {ctx['cpu_temp']}\n"
        f"PUERTOS ABIERTOS: {ctx['ports']}\n"
        f"INTENTOS LOGIN FALLIDOS: {ctx['failed_logins']}\n\n"
        "Proporciona:\n"
        "1. ESTADO: OK / ALERTA / CRÍTICO\n"
        "2. Riesgos detectados (máx. 2)\n"
        "3. Acción recomendada más urgente\n\n"
        "Máximo 5 líneas, en español:"
    )
    t = time.time()
    ask_ollama(prompt)
    print(f"\n⏱️  {time.time()-t:.1f}s")


def cmd_status(ctx):
    """Muestra el estado del sistema sin IA."""
    print("📊 Estado del sistema:")
    print(f"  Hostname  : {ctx['hostname']}")
    print(f"  IP        : {ctx['ip']}")
    print(f"  Uptime    : {ctx['uptime']}")
    print(f"  Carga     : {ctx['load']}")
    print(f"  RAM       : {ctx['ram']}")
    print(f"  CPU Temp  : {ctx['cpu_temp']}")
    print(f"  Disco /   : {ctx['disk']}")
    print(f"  Puertos   : {ctx['ports']}")
    print(f"  Fallos SSH: {ctx['failed_logins']}")


def cmd_interactive(ctx):
    """Modo conversación interactiva."""
    print("Modo interactivo — escribe 'salir' o Ctrl+C para terminar\n")
    while True:
        try:
            pregunta = input("💬 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Hasta luego.")
            break

        if not pregunta:
            continue
        if pregunta.lower() in ("exit", "quit", "salir", "q"):
            print("👋 Hasta luego.")
            break

        t = time.time()
        ask_ollama(build_context_prompt(ctx, pregunta))
        print(f"⏱️  {time.time()-t:.1f}s")


def cmd_ask(ctx, pregunta):
    """Pregunta directa con contexto del sistema."""
    print(f"💬 {pregunta}\n")
    t = time.time()
    ask_ollama(build_context_prompt(ctx, pregunta))
    print(f"\n⏱️  {time.time()-t:.1f}s")

# ── Entrypoint ────────────────────────────────────────────────────────────────

def print_header(ctx, models):
    print("=" * 54)
    print(f"  🦞 Edge Sec Agent v{VERSION}")
    print(f"  📡 Modelo : {MODEL}")
    print(f"  🟢 Ollama : {', '.join(models)}")
    print(f"  🖥️  Sistema: {ctx['hostname']} | {ctx['ip']}")
    print(f"  💾 RAM    : {ctx['ram']}  🌡️  CPU: {ctx['cpu_temp']}")
    print("=" * 54)


USAGE = """\
Uso:
  python3 agent.py                   — modo interactivo
  python3 agent.py --security        — análisis de seguridad
  python3 agent.py --status          — estado del sistema (sin IA)
  python3 agent.py "tu pregunta"     — pregunta directa

Variables de entorno:
  EDGE_MODEL        (default: tinyllama:1.1b)
  EDGE_MAX_TOKENS   (default: 120)
  EDGE_TIMEOUT      (default: 180)
  EDGE_TEMP         (default: 0.3)
"""


def main():
    args = sys.argv[1:]

    if args and args[0] in ("-h", "--help"):
        print(USAGE)
        sys.exit(0)

    # Verificar Ollama
    ok, info = check_ollama()
    if not ok:
        print(f"❌ Ollama no disponible: {info}")
        print("   Solución: systemctl restart ollama && sleep 20")
        sys.exit(1)

    # Contexto del sistema (siempre)
    ctx = get_system_context()
    print_header(ctx, info)
    print()

    if not args:
        cmd_interactive(ctx)
    elif args[0] == "--security":
        cmd_security(ctx)
    elif args[0] == "--status":
        cmd_status(ctx)
    else:
        cmd_ask(ctx, " ".join(args))


if __name__ == "__main__":
    main()