#!/usr/bin/env python3
"""Edge Sec Agent v0.4.0 — Asistente personal DevSecOps"""

import urllib.request, json, subprocess, sys, time, os

OLLAMA_URL  = "http://localhost:11434/api/generate"
OLLAMA_TAGS = "http://localhost:11434/api/tags"
MODEL       = os.getenv("EDGE_MODEL", "tinyllama:1.1b")
MAX_TOKENS  = int(os.getenv("EDGE_MAX_TOKENS", "150"))
TIMEOUT     = int(os.getenv("EDGE_TIMEOUT", "180"))
VERSION     = "0.4.0"

def run(cmd, t=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=t)
        return r.stdout.strip() or r.stderr.strip() or "-"
    except:
        return "-"

def get_ctx():
    raw = run("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
    try: temp = f"{int(raw)/1000:.1f}C"
    except: temp = "?"
    ports = run("ss -tlnp 2>/dev/null | awk 'NR>1{print $4}' | rev | cut -d: -f1 | rev | sort -n | uniq | tr '\n' ' '")
    return {
        "ip":      run("hostname -I").split()[0],
        "ram":     run("free -h | awk '/Mem/{print $3\"/\"$2}'"),
        "temp":    temp,
        "disk":    run("df -h / | awk 'NR==2{print $3\"/\"$2\" (\"$5\")\"}' "),
        "uptime":  run("uptime -p"),
        "ports":   ports.strip() or "ninguno",
        "failed":  run("lastb 2>/dev/null | wc -l").strip(),
        "load":    run("uptime | awk -F'load average:' '{print $2}'").strip(),
    }

def check_ollama():
    try:
        with urllib.request.urlopen(urllib.request.Request(OLLAMA_TAGS), timeout=5) as r:
            data = json.loads(r.read())
            return True, [m["name"] for m in data.get("models", [])]
    except Exception as e:
        return False, str(e)

def ask(prompt):
    payload = json.dumps({
        "model": MODEL, "prompt": prompt, "stream": True,
        "options": {"num_predict": MAX_TOKENS, "temperature": 0.4}
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=payload,
                                  headers={"Content-Type": "application/json"})
    result = ""
    print("\033[36m🤖 \033[0m", end="", flush=True)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            for line in resp:
                line = line.strip()
                if not line: continue
                try: chunk = json.loads(line)
                except: continue
                token = chunk.get("response", "")
                print(token, end="", flush=True)
                result += token
                if chunk.get("done"): break
    except Exception as e:
        print(f"\n❌ {e}")
    print()
    return result

def build_prompt(ctx, historial, pregunta):
    ctx_str = (
        f"IP:{ctx['ip']} RAM:{ctx['ram']} CPU:{ctx['temp']} "
        f"Disco:{ctx['disk']} Uptime:{ctx['uptime']} "
        f"Puertos abiertos:{ctx['ports']} Fallos login:{ctx['failed']}"
    )
    hist_str = ""
    for h in historial[-4:]:  # últimas 4 rondas
        hist_str += f"Usuario: {h['q']}\nAsistente: {h['a']}\n"

    return (
        f"Eres Sec, asistente DevSecOps de Jaime. "
        f"Sistema actual: {ctx_str}. "
        f"Responde siempre en español, de forma directa y técnica. "
        f"{hist_str}"
        f"Usuario: {pregunta}\nAsistente:"
    )

def header(ctx, models):
    print("\033[1m" + "═" * 52 + "\033[0m")
    print(f"\033[1m  🦞 Edge Sec Agent v{VERSION}\033[0m")
    print(f"  📡 {MODEL}  |  🟢 Ollama OK")
    print(f"  🖥️  {ctx['ip']}  |  💾 {ctx['ram']}  |  🌡️  {ctx['temp']}")
    print(f"  🔌 Puertos: {ctx['ports']}")
    print(f"  ⚠️  Fallos SSH: {ctx['failed']}")
    print("\033[1m" + "═" * 52 + "\033[0m")

def main():
    ok, models = check_ollama()
    if not ok:
        print(f"❌ Ollama no responde: {models}")
        print("   Ejecuta: systemctl restart ollama && sleep 25")
        sys.exit(1)

    ctx = get_ctx()
    header(ctx, models)

    args = sys.argv[1:]

    # Pregunta directa (no interactivo)
    if args and args[0] not in ("--chat", "--status", "--security"):
        pregunta = " ".join(args)
        print(f"\n\033[33m💬 {pregunta}\033[0m")
        t = time.time()
        ask(build_prompt(ctx, [], pregunta))
        print(f"\033[90m⏱  {time.time()-t:.1f}s\033[0m\n")
        return

    if args and args[0] == "--status":
        print(f"\nUptime : {ctx['uptime']}")
        print(f"Carga  : {ctx['load']}")
        print(f"Disco  : {ctx['disk']}")
        return

    if args and args[0] == "--security":
        pregunta = (
            f"El sistema tiene puertos {ctx['ports']} abiertos y "
            f"{ctx['failed']} intentos de login fallidos. "
            "Indica el riesgo de seguridad y la accion mas urgente."
        )
        t = time.time()
        ask(build_prompt(ctx, [], pregunta))
        print(f"\033[90m⏱  {time.time()-t:.1f}s\033[0m\n")
        return

    # Modo chat (defecto)
    print("\n\033[90mHabla con Sec, tu asistente DevSecOps.")
    print("Comandos: 'estado', 'seguridad', 'salir'\033[0m\n")

    historial = []

    while True:
        try:
            entrada = input("\033[33m💬 Tú: \033[0m").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Hasta luego.")
            break

        if not entrada:
            continue

        if entrada.lower() in ("salir", "exit", "quit", "q"):
            print("👋 Hasta luego.")
            break

        if entrada.lower() == "estado":
            ctx = get_ctx()  # refrescar
            print(f"  IP:{ctx['ip']} RAM:{ctx['ram']} CPU:{ctx['temp']} Disco:{ctx['disk']}")
            print(f"  Puertos:{ctx['ports']} Fallos:{ctx['failed']}")
            continue

        if entrada.lower() == "seguridad":
            entrada = (
                f"El sistema tiene puertos {ctx['ports']} abiertos y "
                f"{ctx['failed']} intentos de login fallidos. "
                "Cual es el mayor riesgo y que hago?"
            )

        t = time.time()
        prompt = build_prompt(ctx, historial, entrada)
        respuesta = ask(prompt)
        print(f"\033[90m⏱  {time.time()-t:.1f}s\033[0m\n")

        historial.append({"q": entrada, "a": respuesta.strip()})

if __name__ == "__main__":
    main()
