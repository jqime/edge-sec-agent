#!/usr/bin/env python3
import subprocess, sys, json, os, time

# Configuración
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "tinyllama:1.1b"
TIMEOUT_CMD = 10          # comandos del sistema
TIMEOUT_IA = 25           # esperar a Ollama 25 segundos

def run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=TIMEOUT_CMD)
        out = r.stdout.strip()
        return out[:2000] if out else (r.stderr.strip()[:200] or "-")
    except:
        return "[error]"

def comandos_reales(pregunta):
    """Ejecuta comandos reales según palabras clave y devuelve la salida cruda"""
    p = pregunta.lower()
    if any(w in p for w in ["red", "dispositivos", "escanea", "scan", "nmap", "arp"]):
        return run("arp -a 2>/dev/null || ip neigh")
    if any(w in p for w in ["puertos", "escuchando", "listening", "servicios abiertos"]):
        return run("ss -tlnp")
    if any(w in p for w in ["procesos", "cpu", "top", "ps"]):
        return run("ps aux --sort=-%cpu | head -8")
    if any(w in p for w in ["ram", "memoria", "free"]):
        return run("free -h")
    if any(w in p for w in ["temp", "temperatura", "cpu"]):
        raw = run("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
        try:
            return f"{int(raw)/1000:.1f}C" if raw else "?"
        except:
            return "?"
    if any(w in p for w in ["fallos", "ssh", "failed login"]):
        return run("lastb 2>/dev/null | wc -l") + " intentos fallidos"
    if any(w in p for w in ["estado", "status", "sistema"]):
        ip = run("hostname -I | awk '{print $1}'")
        ram = run("free -h | awk '/Mem/{print $3\"/\"$2}'")
        temp = run("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
        tempc = f"{int(temp)/1000:.1f}C" if temp else "?"
        fail = run("lastb 2>/dev/null | wc -l")
        return f"IP {ip} | RAM {ram} | Temp {tempc} | Fallos SSH: {fail}"
    return None  # no es un comando reconocido

def ask_ollama(prompt):
    """Intenta obtener respuesta de Ollama con timeout"""
    import urllib.request, json
    data = json.dumps({
        "model": MODEL,
        "prompt": prompt[:500],
        "stream": False,
        "options": {"num_predict": 150, "temperature": 0.2}
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_IA) as resp:
            return json.loads(resp.read()).get("response", "")
    except Exception as e:
        return None

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 agent_hibrido.py 'pregunta'")
        return
    pregunta = " ".join(sys.argv[1:])
    
    # 1. Intentar respuesta directa con comandos reales
    datos = comandos_reales(pregunta)
    if datos:
        print(f"📡 {datos}")
        return
    
    # 2. Si no es comando conocido, usar IA (pero con respaldo)
    print("🤔 Pregunta conversacional, consultando IA...")
    ctx = {
        "ip": run("hostname -I | awk '{print $1}'"),
        "ram": run("free -h | awk '/Mem/{print $3\"/\"$2}'"),
        "temp": run("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null"),
        "ports": run("ss -tlnp | awk 'NR>1{print $4}' | rev | cut -d: -f1 | rev | sort -n | uniq | tr '\n' ' '")[:100],
        "failed": run("lastb 2>/dev/null | wc -l")
    }
    if ctx["temp"]:
        ctx["temp"] = f"{int(ctx['temp'])/1000:.1f}C"
    prompt = f"Sistema: IP {ctx['ip']}, RAM {ctx['ram']}, temperatura {ctx['temp']}, puertos {ctx['ports']}, fallos SSH {ctx['failed']}. Pregunta: {pregunta}. Respuesta breve."
    resp = ask_ollama(prompt)
    if resp:
        print(f"🤖 {resp}")
    else:
        print("⚠️ No se pudo obtener respuesta de IA. Intenta un comando como: 'red', 'puertos', 'status'.")

if __name__ == "__main__":
    main()
