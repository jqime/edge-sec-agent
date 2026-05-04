#!/usr/bin/env python3
import subprocess, json, sys, os, time, re
from datetime import datetime

MODEL = os.environ.get("EDGE_MODEL", "tinyllama:1.1b")
MAX_TOKENS = int(os.environ.get("EDGE_MAX_TOKENS", "120"))
HTTP_TIMEOUT = int(os.environ.get("EDGE_TIMEOUT", "180"))

def run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() or r.stderr.strip() or "-"
    except:
        return "-"

def get_ctx():
    raw = run("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
    try: temp = f"{int(raw)/1000:.1f}C"
    except: temp = "?"
    ports = run("ss -tlnp 2>/dev/null | awk 'NR>1{print $4}' | rev | cut -d: -f1 | rev | sort -n | uniq | tr '\n' ' '")
    return {
        "ip": run("hostname -I").split()[0],
        "ram": run("free -h | awk '/Mem/{print $3\"/\"$2}'"),
        "temp": temp,
        "ports": ports.strip() or "ninguno",
        "failed": run("lastb 2>/dev/null | wc -l").strip(),
    }

def _count_ssh_failures():
    paths = os.environ.get("SSH_LOG_PATHS", "/var/log/auth.log,/var/log/secure").split(",")
    total = 0
    for p in paths:
        if os.path.exists(p):
            try:
                with open(p, "r", errors="ignore") as f:
                    total += sum(1 for line in f if "Failed password" in line or "authentication failure" in line.lower())
            except: pass
    return total

def _get_open_ports():
    ports = set()
    for cmd in ["ss -tlnp 2>/dev/null", "netstat -tlnp 2>/dev/null"]:
        try:
            out = run(cmd)
            if out and out.strip() != "-":
                for line in out.splitlines():
                    if "LISTEN" in line:
                        parts = line.split()
                        for token in parts:
                            if ":" in token:
                                port = token.split(":")[-1]
                                if port.isdigit():
                                    ports.add(port)
                if ports:
                    return sorted(ports, key=lambda x: int(x))
        except: pass
    try:
        with open("/proc/net/tcp", "r") as f:
            for line in f.readlines()[1:]:
                fields = line.strip().split()
                if len(fields) >= 2:
                    port_hex = fields[1].split(":")[-1]
                    try: ports.add(str(int(port_hex, 16)))
                    except: pass
        return sorted(ports, key=lambda x: int(x))
    except: return []

def _get_temperature_c():
    for i in range(10):
        path = f"/sys/class/thermal/thermal_zone{i}/temp"
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return int(f.read().strip())/1000.0
            except: continue
    return None

def _get_ram_usage_percent():
    try:
        with open("/proc/meminfo", "r") as f:
            total = avail = None
            for line in f:
                if line.startswith("MemTotal:"): total = int(line.split()[1])
                if line.startswith("MemAvailable:"): avail = int(line.split()[1])
            if total and avail:
                return ((total - avail)/total)*100.0
    except: pass
    return None

def _compute_score(ssh, ports, temp, ram):
    penalties = min(ssh*2, 60)
    allowed = {22,80,443,25,53}
    risk_ports = sum(1 for p in ports if int(p) not in allowed)
    penalties += min(risk_ports*8, 40)
    if temp and temp>55: penalties += min((temp-55)*1.5, 25)
    if ram and ram>60: penalties += min((ram-60)*0.8, 25)
    return max(0, 100 - int(penalties))

def _format_report(score, ssh, ports, temp, ram):
    lines = [f"Informe de Seguridad - Puntuación: {score}/100", "Riesgos detectados:"]
    lines.append(f"- SSH fallos: {ssh}")
    lines.append(f"- Puertos abiertos: {', '.join(ports) if ports else 'ninguno'}")
    lines.append(f"- Temperatura CPU: {temp:.1f}C" if temp else "- Temperatura: desconocida")
    lines.append(f"- RAM usado: {ram:.1f}%" if ram else "- RAM: desconocido")
    lines.append("\nRecomendaciones:")
    if ssh>0: lines.append("  • SSH: deshabilitar login por contraseña, usar claves, fail2ban.")
    if ports: lines.append("  • Puertos: cerrar servicios no esenciales, usar firewall.")
    if temp and temp>55: lines.append("  • Temperatura: mejorar refrigeración, reducir carga.")
    if ram and ram>60: lines.append("  • RAM: optimizar procesos, añadir swap.")
    if not (ssh or ports or (temp and temp>55) or (ram and ram>60)):
        lines.append("  • Sistema estable. Mantén monitorización.")
    return "\n".join(lines)

def save_report(text):
    dir_ = os.environ.get("REPORTS_DIR", "/root/edge-sec-agent/reports")
    os.makedirs(dir_, exist_ok=True)
    path = os.path.join(dir_, f"security_{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt")
    with open(path, "w") as f:
        f.write(text)
    return path

def _generate_html_report(score, ssh_failures, open_ports, temp_c, ram_percent, timestamp=None, recommendations=None):
    ts = timestamp or time.strftime("%Y-%m-%d %H:%M:%S")
    ports_str = ", ".join(open_ports) if open_ports else "ninguno"
    temp_str = f"{temp_c:.1f}C" if isinstance(temp_c, (int, float)) else "desconocida"
    ram_str = f"{ram_percent:.1f}%" if isinstance(ram_percent, (int, float)) else "desconocido"
    rec_html = ""
    if recommendations:
        rec_html = "<h3>Recomendaciones</h3><ul>"
        for r in recommendations:
            rec_html += f"<li>{r}</li>"
        rec_html += "</ul>"
    score_class = "green" if score >= 70 else ("orange" if score >= 50 else "red")
    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><title>Informe de Seguridad - {ts}</title>
<style>
body {{ font-family: Arial; margin: 40px; background: #f4f4f4; }}
.container {{ max-width: 800px; margin: auto; background: white; padding: 20px; border-radius: 8px; }}
.score {{ font-size: 2em; }}
.green {{ color: green; }}
.orange {{ color: orange; }}
.red {{ color: red; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background: #ff6b00; color: white; }}
</style>
</head>
<body>
<div class="container">
<h1>Informe de Seguridad</h1>
<p>Fecha: {ts}</p>
<p>Puntuación: <span class="score {score_class}">{score}/100</span></p>
<table>
    <tr><th>Métrica</th><th>Valor</th></tr>
    <tr><td>SSH fallos</td><td>{ssh_failures}</td></tr>
    <tr><td>Puertos abiertos</td><td>{ports_str}</td></tr>
    <tr><td>Temperatura CPU</td><td>{temp_str}</td></tr>
    <tr><td>RAM usado</td><td>{ram_str}</td></tr>
    </table>
    {rec_html}
</div>
</body></html>"""
    return html

def _generate_html_recommendations(ssh_failures, open_ports, temp_c, ram_percent):
    recs = []
    if ssh_failures > 0: recs.append("SSH: usar claves, deshabilitar contraseña, fail2ban.")
    if open_ports: recs.append("Puertos: cerrar servicios no esenciales, usar firewall.")
    if temp_c and temp_c > 55: recs.append("Temperatura alta: mejorar refrigeración.")
    if ram_percent and ram_percent > 60: recs.append("RAM alta: optimizar procesos, añadir swap.")
    if not recs: recs.append("Sistema estable. Mantén monitorización.")
    return recs

def save_html_report(html_text, report_dir=None):
    dirp = report_dir or os.environ.get("REPORTS_DIR", "/root/edge-sec-agent/reports")
    os.makedirs(dirp, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(dirp, f"security_{ts}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_text)
    return path

def cmd_html():
    ssh = _count_ssh_failures()
    ports = _get_open_ports()
    temp = _get_temperature_c()
    ram = _get_ram_usage_percent()
    score = _compute_score(ssh, ports, temp, ram)
    recs = _generate_html_recommendations(ssh, ports, temp, ram)
    html = _generate_html_report(score, ssh, ports, temp, ram, None, recs)
    path = save_html_report(html)
    print(f"[HTML] Informe HTML guardado en: {path}")
    return path

def cmd_security(json_output=False):
    try:
        ssh = _count_ssh_failures()
        ports = _get_open_ports()
        temp = _get_temperature_c()
        ram = _get_ram_usage_percent()
        score = _compute_score(ssh, ports, temp, ram)
        if json_output:
            print(json.dumps({"score":score,"ssh_failures":ssh,"open_ports":ports,"temp_c":temp,"ram_percent":ram,"report_path":None}))
            return
        txt = _format_report(score, ssh, ports, temp, ram)
        path = save_report(txt)
        print(txt)
        print(f"\nInforme guardado en: {path}")
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)

def main():
    args = sys.argv[1:]
    if "--html" in args:
        cmd_html()
        return
    json_output = "--json" in args
    if "--security" in args:
        cmd_security(json_output=json_output)
        return
    print("Uso: sec-agent --security [--json] | --html")

if __name__ == "__main__":
    main()
