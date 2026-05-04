#!/usr/bin/env python3
import json, subprocess, sys, os, urllib.request, time

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "tinyllama:1.1b"           # Rápido y ligero
MAX_TOKENS = 300
HTTP_TIMEOUT = 60                  # 1 minuto para Ollama
CMD_TIMEOUT = 15                   # 15 segundos por comando

def run(cmd, timeout=CMD_TIMEOUT):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        out = r.stdout.strip()
        return out[:2000] if out else (r.stderr.strip()[:200] or "-")
    except:
        return "[fallo]"

def execute_tool(cmd):
    print(f"\n\033[90m  ⚙️  {cmd}\033[0m", flush=True)
    return run(cmd)

def get_ctx():
    raw = run("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
    try:
        temp = f"{int(raw)/1000:.1f}C"
    except:
        temp = "?"
    ports = run("ss -tlnp 2>/dev/null | awk 'NR>1{print $4}' | rev | cut -d: -f1 | rev | sort -n | uniq | tr '\n' ' '")
    return {
        "ip": run("hostname -I | awk '{print $1}'"),
        "ram": run("free -h | awk '/Mem/{print $3\"/\"$2}'"),
        "temp": temp,
        "ports": ports.strip() or "ninguno",
        "failed": run("lastb 2>/dev/null | wc -l").strip(),
    }

def ask_ollama(prompt):
    data = json.dumps({"model": MODEL, "prompt": prompt, "stream": False,
                       "options": {"num_predict": MAX_TOKENS, "temperature": 0.2}}).encode()
    req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read()).get("response", "")
    except Exception as e:
        return f"[Ollama: {e}]"

def build_prompt(ctx, pregunta, tool_output):
    sys_info = f"IP:{ctx['ip']} RAM:{ctx['ram']} Temp:{ctx['temp']} Puertos:{ctx['ports']} FallosSSH:{ctx['failed']}"
    datos = f"\n--- DATOS REALES ---\n{tool_output}\n---" if tool_output else ""
    return f"""Eres Sec (DevSecOps). Usa SOLO los datos reales. No inventes.
Sistema: {sys_info}{datos}
Jaime: {pregunta}
Respuesta técnica breve en español:"""

def main():
    ctx = get_ctx()
    print(f"Edge Sec Agent | {ctx['ip']} | {ctx['ram']} | {ctx['temp']} | Puertos: {ctx['ports']}")
    args = sys.argv[1:]
    if not args:
        print("Uso: python3 agent.py 'pregunta'")
        return
    pregunta = " ".join(args)
    tool_output = ""
    q = pregunta.lower()
    if any(w in q for w in ["nmap", "dispositivos", "red", "escanea", "scan"]):
        tool_output = execute_tool("arp -a 2>/dev/null || ip neigh")
    if any(w in q for w in ["puertos", "escuchando"]):
        tool_output += "\n\n" + execute_tool("ss -tlnp")
    if any(w in q for w in ["procesos", "cpu"]):
        tool_output += "\n\n" + execute_tool("ps aux --sort=-%cpu | head -5")
    if any(w in q for w in ["logs", "ssh"]):
        tool_output += "\n\n" + execute_tool("journalctl _COMM=sshd --since '1h ago' -n 10 --no-pager 2>/dev/null")
    prompt = build_prompt(ctx, pregunta, tool_output)
    print("\n🤖 Sec:", end=" ", flush=True)
    resp = ask_ollama(prompt)
    print(resp)

if __name__ == "__main__":
    main()
