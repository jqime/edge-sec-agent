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
from datetime import datetime

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

# Funcionalidad de seguridad auxiliar (cmd_security)
def _count_ssh_failures():
    logs = []
    paths = ["/var/log/auth.log", "/var/log/auth.log.1", "/var/log/secure", "/var/log/secure.1"]
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p, "r", errors="ignore") as f:
                    for line in f:
                        if "Failed password" in line or "authentication failure" in line.lower():
                            logs.append(line)
            except Exception:
                continue
    return len(logs)

def _get_open_ports():
    ports = set()
    out = run("ss -tlnp 2>/dev/null")
    if not out or out.strip() == "-":
        return sorted(list(ports))
    for line in out.splitlines():
        if "LISTEN" not in line:
            continue
        parts = line.strip().split()
        if len(parts) >= 4:
            local = parts[3]
            if ":" in local:
                port = local.split(":")[-1]
                if port.isdigit():
                    ports.add(int(port))
    return sorted(list(ports))

def _get_temperature_c():
    for i in range(0, 10):
        path = f"/sys/class/thermal/thermal_zone{i}/temp"
        if os.path.exists(path):
            try:
                v = int(open(path).read().strip())
                return v / 1000.0
            except Exception:
                continue
    return None

def _get_ram_usage_percent():
    try:
        with open("/proc/meminfo", "r") as f:
            total = None
            avail = None
            for line in f:
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1])
                if line.startswith("MemAvailable:"):
                    avail = int(line.split()[1])
            if total and avail is not None:
                used = total - avail
                return (used / total) * 100.0
    except Exception:
        pass
    return None

def _compute_security_score(ssh_failures, open_ports, temp_c, ram_percent):
    penalties = 0.0
    penalties += min(ssh_failures * 2.0, 60.0)
    allowed = {22, 80, 443, 25, 53}
    risk_open_ports = sum(1 for p in open_ports if p not in allowed)
    penalties += min(risk_open_ports * 8.0, 40.0)
    if temp_c is not None and temp_c > 55:
        penalties += min((temp_c - 55) * 1.5, 25.0)
    if ram_percent is not None and ram_percent > 60:
        penalties += min((ram_percent - 60) * 0.8, 25.0)
    score = max(0, 100 - int(penalties))
    return score

def _format_security_report(score, ssh_f, open_ports, temp_c, ram_p):
    lines = []
    lines.append(f"Informe de Seguridad - Puntuación: {score}/100")
    lines.append("Riesgos detectados:")
    lines.append(f"- SSH: fallos observados = {ssh_f}")
    ports_str = ", ".join(map(str, open_ports)) if open_ports else "ninguno"
    lines.append(f"- Puertos abiertos: {ports_str}")
    lines.append(f"- Temperatura CPU: {temp_c:.1f}C" if temp_c is not None else "- Temperatura CPU: desconocida")
    lines.append(f"- RAM usado: {ram_p:.1f}%" if ram_p is not None else "- RAM usado: desconocido")
    lines.append("")
    lines.append("Recomendaciones específicas:")
    recs = []
    if ssh_f > 0:
        recs.append("- SSH: usar autenticación por clave, deshabilitar root y login por contraseña, activar fail2ban o similares.")
        recs.append("- SSH: considerar cambiar puerto SSH y/o usar 2FA si disponible.")
    if open_ports:
        recs.append("- Puertos abiertos: cerrar servicios no esenciales, usar firewall para limitar acceso.")
        recs.append("- Revisa servicios en puertos no estándar y valida necesidad real.")
    if temp_c is not None and temp_c > 55:
        recs.append("- Temperatura alta: mejora refrigeración y revisa procesos que consumen CPU.")
    if ram_p is not None and ram_p > 60:
        recs.append("- RAM alta utilización: optimizar procesos, considerar swap/zram, revisar fuga de memoria.")
    if not recs:
        recs.append("- El sistema parece estable; mantener monitoreo periódico.")
    for r in recs:
        lines.append("  " + r)
    return "\n".join(lines)

def save_security_report(text):
    dirp = "/root/edge-sec-agent/reports"
    os.makedirs(dirp, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = f"{dirp}/security_{ts}.txt"
    with open(path, "w") as f:
        f.write(text)
    return path

def cmd_security():
    ssh_failures = _count_ssh_failures()
    open_ports = _get_open_ports()
    temp_c = _get_temperature_c()
    ram_percent = _get_ram_usage_percent()
    score = _compute_security_score(ssh_failures, open_ports, temp_c, ram_percent)
    report_text = _format_security_report(score, ssh_failures, open_ports, temp_c, ram_percent)
    report_path = save_security_report(report_text)
    print(report_text)
    print(f"\nInforme guardado en: {report_path}")
    return {
        "score": score,
        "ssh_failures": ssh_failures,
        "open_ports": open_ports,
        "temp_c": temp_c,
        "ram_percent": ram_percent,
        "report_path": report_path,
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
    return f"""Eres Sec, asistente DevSecOps. Responde siempre en español y en formato de viñetas. Responde usando EXCLUSIVAMENTE los datos reales que aparecen abajo. No inventes números ni información.

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

    # Comando dedicado de seguridad
    if "--security" in args:
        cmd_security()
        return

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
