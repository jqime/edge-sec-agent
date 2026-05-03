#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Edge Sec Agent v1.0.0 - Agente DevSecOps autónomo con memoria, planificación y MCP
Funciona 100% local con Ollama en Orange Pi Zero 3
"""

import json
import subprocess
import sys
import os
import urllib.request
import time
import hashlib

# ========== CONFIGURACIÓN ==========
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = os.getenv("EDGE_MODEL", "qwen2.5:3b")
CLASSIFIER_MODEL = "tinyllama:1.1b"          # para clasificación rápida
MAX_TOKENS = 500
HTTP_TIMEOUT = 180                           # para llamadas a Ollama (3 min)
CMD_TIMEOUT = 120                            # para comandos del sistema
MEMORY_FILE = "/root/edge-sec-agent/memory.json"
MCP_TOOLS_DIR = "/root/edge-sec-agent/mcp_tools"
os.makedirs(MCP_TOOLS_DIR, exist_ok=True)

# ========== MEMORIA PERSISTENTE ==========
def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE) as f:
            return json.load(f)
    return {"history": [], "cmd_cache": {}}

def save_memory(mem):
    with open(MEMORY_FILE, "w") as f:
        json.dump(mem, f, indent=2)

def remember_cmd(cmd, output):
    mem = load_memory()
    cmd_hash = hashlib.md5(cmd.encode()).hexdigest()
    mem["cmd_cache"][cmd_hash] = {"cmd": cmd, "output": output[:3000], "timestamp": time.time()}
    if len(mem["cmd_cache"]) > 50:
        oldest = min(mem["cmd_cache"].items(), key=lambda x: x[1]["timestamp"])
        del mem["cmd_cache"][oldest[0]]
    save_memory(mem)

def get_cached_cmd(cmd, max_age=120):
    mem = load_memory()
    cmd_hash = hashlib.md5(cmd.encode()).hexdigest()
    if cmd_hash in mem["cmd_cache"]:
        entry = mem["cmd_cache"][cmd_hash]
        if time.time() - entry["timestamp"] < max_age:
            return entry["output"]
    return None

# ========== EJECUCIÓN DE COMANDOS ==========
def run(cmd, timeout=CMD_TIMEOUT):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        out = r.stdout.strip()
        return out[:4000] if out else (r.stderr.strip()[:500] or "-")
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT excedido ({timeout}s)]"
    except Exception as e:
        return f"[error: {e}]"

def is_safe(cmd):
    dangerous = ["rm ", "dd ", "mkfs", "shutdown", "reboot", "chmod 777", "> /dev", "mkfs", "format"]
    return not any(d in cmd.lower() for d in dangerous)

def execute_tool(cmd, use_cache=True):
    if not is_safe(cmd):
        return f"[BLOQUEADO] {cmd}"
    if use_cache:
        cached = get_cached_cmd(cmd, max_age=120)
        if cached:
            print(f"\n\033[90m  💾 En caché (últimos 2min): {cmd}\033[0m", flush=True)
            return cached
    print(f"\n\033[90m  ⚙️  {cmd}\033[0m", flush=True)
    result = run(cmd)
    remember_cmd(cmd, result)
    return result

# ========== CONTEXTO DEL SISTEMA ==========
def get_ctx():
    raw = run("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
    try:
        temp = f"{int(raw)/1000:.1f}C"
    except:
        temp = "?"
    ports = run("ss -tlnp 2>/dev/null | awk 'NR>1{print $4}' | rev | cut -d: -f1 | rev | sort -n | uniq | tr '\n' ' '")
    net_iface = run("ip route | awk '/default/{print $5}' | head -1")
    net_range = run(f"ip -o -f inet addr show {net_iface} 2>/dev/null | awk '{{print $4}}' | head -1")
    return {
        "ip": run("hostname -I | awk '{print $1}'"),
        "ram": run("free -h | awk '/Mem/{print $3\"/\"$2}'"),
        "temp": temp,
        "ports": ports.strip() or "ninguno",
        "failed": run("lastb 2>/dev/null | wc -l").strip(),
        "net_range": net_range.strip() or "192.168.1.0/24",
    }

# ========== LLAMADA A OLLAMA ==========
def ask_ollama(prompt, model=None, max_tokens=MAX_TOKENS, temp=0.2):
    m = model or MODEL
    data = json.dumps({
        "model": m,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": temp}
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read()).get("response", "")
    except Exception as e:
        return f"[Error Ollama: {e}]"

# ========== CLASIFICADOR DE INTENCIÓN (rápido, con tinyllama) ==========
def classify_intent(user_input):
    inp = user_input.lower()
    # Reglas rápidas para evitar llamar al modelo
    if any(w in inp for w in ["nmap", "scan", "escanea", "dispositivos", "puertos", "logs", "procesos", "firewall", "fail2ban"]):
        return "direct_execution"
    if any(w in inp for w in ["instala", "configura", "crea", "despliega", "elimina", "actualiza"]):
        return "needs_planning"
    if any(w in inp for w in ["qué", "cómo", "cuál", "explica", "dime"]):
        return "conversational"
    # Si no está claro, usar modelo pequeño
    prompt = f"Clasifica esta consulta en una sola palabra: 'conversational', 'direct_execution' o 'needs_planning': {user_input}"
    resp = ask_ollama(prompt, model=CLASSIFIER_MODEL, max_tokens=10, temp=0)
    resp = resp.strip().lower()
    if "direct" in resp:
        return "direct_execution"
    if "plan" in resp:
        return "needs_planning"
    return "conversational"

# ========== PLANIFICADOR DE TAREAS ==========
def plan_task(user_input, ctx):
    ctx_info = f"IP {ctx['ip']}, puertos abiertos {ctx['ports']}, RAM {ctx['ram']}"
    prompt = f"""Eres un planificador DevSecOps. Descompón la siguiente tarea en una lista de comandos de shell (uno por línea). No des explicaciones adicionales. Usa los datos del sistema si los necesitas.

Contexto sistema: {ctx_info}
Tarea: {user_input}

Comandos:"""
    plan_text = ask_ollama(prompt, model=MODEL, max_tokens=300, temp=0.1)
    steps = [line.strip() for line in plan_text.split("\n") if line.strip() and not line.startswith("#")]
    return steps[:5]

# ========== MCP (herramientas externas) ==========
def mcp_call(tool_name, args=""):
    script_path = os.path.join(MCP_TOOLS_DIR, tool_name)
    if not os.path.exists(script_path):
        return f"[MCP] Herramienta '{tool_name}' no encontrada"
    if not os.access(script_path, os.X_OK):
        os.chmod(script_path, 0o755)
    cmd = f"{script_path} {args}".strip()
    return run(cmd, timeout=CMD_TIMEOUT)

# ========== DETECCIÓN Y EJECUCIÓN AUTOMÁTICA ==========
def detect_and_execute(pregunta, ctx):
    q_low = pregunta.lower()
    output = ""
    if any(w in q_low for w in ["nmap", "dispositivos", "red", "escanea", "scan"]):
        output = execute_tool(f"arp -a 2>/dev/null || nmap -sn {ctx['net_range']} 2>/dev/null")
    if any(w in q_low for w in ["puertos", "escuchando", "servicios abiertos"]):
        output += "\n\n" + execute_tool("ss -tlnp")
    if any(w in q_low for w in ["logs", "ssh", "intentos", "fallos"]):
        output += "\n\n" + execute_tool("journalctl _COMM=sshd --since '1h ago' -n 30 --no-pager 2>/dev/null | tail -20")
    if any(w in q_low for w in ["procesos", "cpu", "memoria"]):
        output += "\n\n" + execute_tool("ps aux --sort=-%cpu | head -10")
    if any(w in q_low for w in ["firewall", "ufw", "fail2ban"]):
        output += "\n\n" + execute_tool("ufw status 2>/dev/null")
        output += "\n\n" + execute_tool("fail2ban-client status 2>/dev/null")
    return output

# ========== CONSTRUCCIÓN DEL PROMPT CON HISTORIAL ==========
def build_prompt(ctx, pregunta, tool_output, historial):
    sys_info = f"IP:{ctx['ip']} | RAM:{ctx['ram']} | Temp CPU:{ctx['temp']} | Puertos:{ctx['ports']} | Fallos SSH:{ctx['failed']}"
    datos = f"\n--- RESULTADO REAL DEL COMANDO ---\n{tool_output}\n--- FIN ---" if tool_output else "\n(No se ejecutaron comandos adicionales)"
    hist_text = ""
    for h in historial[-5:]:
        hist_text += f"Jaime: {h['q']}\nSec: {h['a']}\n"
    return f"""Eres Sec, asistente DevSecOps. Responde usando EXCLUSIVAMENTE los datos reales que aparecen abajo. No inventes números ni información.

Datos del sistema actual: {sys_info}
{datos}

Historial reciente:
{hist_text}

Pregunta de Jaime: {pregunta}

Respuesta técnica en español, basada solo en los datos reales y en el historial si es relevante:"""

# ========== MODO PRINCIPAL ==========
def main():
    ctx = get_ctx()
    mem = load_memory()
    historial = mem.get("history", [])
    args = sys.argv[1:]

    # Modo de una sola pregunta
    if args and args[0] not in ("--chat", "--interactive"):
        pregunta = " ".join(args)
        tool_output = detect_and_execute(pregunta, ctx)
        prompt = build_prompt(ctx, pregunta, tool_output, historial)
        respuesta = ask_ollama(prompt)
        print(f"\n🤖 Sec: {respuesta}")
        historial.append({"q": pregunta, "a": respuesta, "t": time.time()})
        mem["history"] = historial[-50:]
        save_memory(mem)
        return

    # Modo chat interactivo
    print("\n\033[1m" + "═" * 54 + "\033[0m")
    print(f"\033[1m  🦞 Edge Sec Agent v1.0.0  |  modelo: {MODEL}\033[0m")
    print(f"  🖥️  {ctx['ip']}  |  💾 {ctx['ram']}  |  🌡️  {ctx['temp']}")
    print(f"  🔌 Puertos: {ctx['ports']}  |  ⚠️  Fallos SSH: {ctx['failed']}")
    print("\033[1m" + "═" * 54 + "\033[0m")
    print("\n\033[90mModo chat con memoria. Escribe 'salir' para terminar.\033[0m")

    while True:
        try:
            entrada = input("\n\033[33m💬 Tú: \033[0m").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Hasta luego.")
            break
        if entrada.lower() in ("salir", "exit", "q"):
            print("👋 Hasta luego.")
            break
        if not entrada:
            continue

        # Clasificar intención
        intent = classify_intent(entrada)

        if intent == "direct_execution":
            print("\n\033[90m[Ejecución directa]\033[0m")
            tool_output = detect_and_execute(entrada, ctx)
            if not tool_output.strip():
                tool_output = "(No se ejecutó ningún comando relevante)"
        elif intent == "needs_planning":
            print("\n\033[35m📋 Planificando tarea...\033[0m")
            steps = plan_task(entrada, ctx)
            if not steps:
                print("No se pudo generar un plan. Responderé como conversación.")
                tool_output = ""
            else:
                print("\n\033[36mPlan generado:\033[0m")
                for i, step in enumerate(steps, 1):
                    print(f"  {i}. {step}")
                confirm = input("¿Ejecutar estos pasos? (s/n): ").strip().lower()
                if confirm in ('s', 'si', 'sí', 'y', 'yes'):
                    results = []
                    for step in steps:
                        print(f"\n\033[90m▶️ {step}\033[0m")
                        res = execute_tool(step, use_cache=False)
                        results.append(f"$ {step}\n{res[:500]}")
                    tool_output = "\n\n".join(results)
                else:
                    tool_output = "(Plan cancelado por el usuario)"
        else:  # conversational
            tool_output = ""

        prompt = build_prompt(ctx, entrada, tool_output, historial)
        respuesta = ask_ollama(prompt)
        print(f"\n🤖 Sec: {respuesta}")

        historial.append({"q": entrada, "a": respuesta, "t": time.time()})
        if len(historial) > 50:
            historial = historial[-50:]
        mem["history"] = historial
        save_memory(mem)

if __name__ == "__main__":
    main()
