#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Edge Sec Agent - versión extendida Phase 2/3
Incluye:
- Persistencia en SQLite de ejecuciones (history)
- Generación de informe HTML con gráfico de 7 días (Chart.js)
- API de historial/queries para dashboard
- Soporte a --html, --security y --json
- Historial en SQLite y funciones de historial last_days
- Secrets cargados desde /root/edge-sec-agent/secrets.env
"""

import json, sqlite3, subprocess, sys, os, urllib.request, time, hashlib, re
from datetime import datetime

MODEL = os.environ.get("EDGE_MODEL", "tinyllama:1.1b")
MAX_TOKENS = int(os.environ.get("EDGE_MAX_TOKENS", "120"))
HTTP_TIMEOUT = int(os.environ.get("EDGE_TIMEOUT", "180"))
DB_PATH = "/root/edge-sec-agent/data/history.db"
REPORTS_DIR = os.environ.get("REPORTS_DIR", "/root/edge-sec-agent/reports")

SECRETS_PATH = "/root/edge-sec-agent/secrets.env"
if os.path.exists(SECRETS_PATH):
    try:
        with open(SECRETS_PATH) as f:
            exec(f.read(), globals())
    except Exception:
        pass

def _ensure_history_db():
    os.makedirs("/root/edge-sec-agent/data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            score INTEGER,
            ssh_failures INTEGER,
            open_ports TEXT,
            temp_c REAL,
            ram_percent REAL
        )
    """)
    conn.commit()
    conn.close()

def _insert_history(timestamp, score, ssh, ports, temp, ram):
    _ensure_history_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO history (timestamp, score, ssh_failures, open_ports, temp_c, ram_percent)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (timestamp, int(score), int(ssh), ports, float(temp) if temp is not None else None, float(ram) if ram is not None else None))
    conn.commit()
    conn.close()

def _get_last_days_scores(days=7):
    import datetime as dt
    _start = (dt.date.today() - dt.timedelta(days=days-1)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT date(timestamp) as day, AVG(score) as avg_score
        FROM history
        WHERE date(timestamp) >= ?
        GROUP BY day
        ORDER BY day ASC
    """, (_start,))
    rows = cur.fetchall()
    conn.close()
    history = []
    for day, avg_score in rows:
        history.append({"date": day, "score": int(avg_score) if avg_score is not None else 0})
    return history

def run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() or r.stderr.strip() or "-"
    except Exception:
        return "-"

def get_ctx():
    raw = run("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
    try:
        temp = f"{int(raw)/1000:.1f}C"
    except:
        temp = "?"
    ports = run("ss -tlnp 2>/dev/null | awk 'NR>1{print $4}' | rev | cut -d: -f1 | rev | sort -n | uniq | tr '\\n' ' '")
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
            except Exception:
                pass
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
        except:
            pass
    try:
        with open("/proc/net/tcp", "r") as f:
            for line in f.readlines()[1:]:
                fields = line.strip().split()
                if len(fields) >= 2:
                    port_hex = fields[1].split(":")[-1]
                    try: ports.add(str(int(port_hex, 16)))
                    except: pass
        return sorted(ports, key=lambda x: int(x))
    except:
        return []

def _get_temperature_c():
    for i in range(10):
        path = f"/sys/class/thermal/thermal_zone{i}/temp"
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return int(f.read().strip())/1000.0
            except:
                continue
    return None

def _get_ram_usage_percent():
    try:
        with open("/proc/meminfo", "r") as f:
            total = avail = None
            for line in f:
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1])
                if line.startswith("MemAvailable:"):
                    avail = int(line.split()[1])
            if total and avail:
                return ((total - avail)/total)*100.0
    except:
        pass
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

def _generate_html_report(score, ssh_failures, open_ports, temp_c, ram_percent, timestamp=None, recommendations=None, history7=None):
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
    history7_js = "[]"
    history7_html = ""
    if history7:
        history7_js = json.dumps(history7)
        history7_html = f"""
        <div style="margin-top:20px;">
          <canvas id="scoreChart" width="800" height="240"></canvas>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
          const history7 = {history7_js};
          const labels = history7.map(d => d.date);
          const data = history7.map(d => d.score);
          const ctx = document.getElementById('scoreChart');
          new Chart(ctx, {{
            type: 'line',
            data: {{
              labels: labels,
              datasets: [{{
                label: 'Score',
                data: data,
                borderColor: 'rgb(75, 192, 192)',
                fill: false
              }}]
            }},
            options: {{
              responsive: true,
              scales: {{ y: {{ beginAtZero: true, max: 100 }} }}
            }}
          }});
        </script>
        """
    score_class = "green" if score >= 70 else ("orange" if score >= 50 else "red")
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Informe de Seguridad - {ts}</title>
  <style>
    :root {{ --bg: #f7f7f7; --card: #fff; --text: #333; --muted: #555;
             --green: #28a745; --orange: #ff9800; --red: #e74c3c; }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: Arial, sans-serif; background: var(--bg); color: var(--text); margin:0; padding:0; }}
    .container {{ max-width: 1100px; margin: 40px auto; padding: 20px; background: var(--card); border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.05); }}
    h1 {{ text-align: center; color: #2a6bd6; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
    th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
    th {{ background: #f0f0f0; }}
    .score-row td {{ font-weight: bold; font-size: 1.1em; }}
    @media (max-width: 900px) {{ .container { margin: 20px; } }}
  </style>
</head>
<body>
  <div class="container">
    <h1>Informe de Seguridad</h1>
    <div class="meta" style="text-align:center; color:var(--muted)">Fecha y hora: {ts}</div>
    <div style="text-align:center;">
      <span class="score-row">
        <span class="score {score_class}">Puntuación: {score}/100</span>
      </span>
    </div>
    <table aria-label="Métricas">
      <tr><th>Métrica</th><th>Valor</th></tr>
      <tr><td>SSH fallos</tr><td>{ssh_failures}</td></tr>
      <tr><td>Puertos abiertos</tr><td>{ports_str}</td></tr>
      <tr><td>Temperatura CPU</tr><td>{temp_str}</td></tr>
      <tr><td>RAM usado</tr><td>{ram_str}</td></tr>
    </table>
    {rec_html}
    {history7_html}
  </div>
</body>
</html>"""
    return html

def _generate_html_recommendations(ssh_failures, open_ports, temp, ram):
    recs = []
    if ssh_failures > 0:
        recs.append("SSH: usar autenticación por clave, deshabilitar root y login por contraseña, activar fail2ban o similares.")
        recs.append("SSH: considerar cambiar puerto SSH y/o usar 2FA si disponible.")
    if open_ports:
        recs.append("Puertos abiertos: cerrar servicios no esenciales, usar firewall para limitar acceso.")
        recs.append("Revisa servicios en puertos no estándar y valida necesidad real.")
    if temp is not None and temp > 55:
        recs.append("Temperatura alta: mejora refrigeración y revisa procesos que consumen CPU.")
    if ram is not None and ram > 60:
        recs.append("RAM alta utilización: optimizar procesos, considerar swap/zram, revisar fuga de memoria.")
    if not recs:
        recs.append("El sistema parece estable; mantener monitoreo.")
    return recs

def save_html_report(html_text, report_dir=None):
    dirp = report_dir or REPORTS_DIR
    os.makedirs(dirp, exist_ok=True)
    path = os.path.join(dirp, f"security_{datetime.now().strftime('%Y%m%d-%H%M%S')}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_text)
    return path

def cmd_html():
    ssh = _count_ssh_failures()
    ports = _get_open_ports()
    temp = _get_temperature_c()
    ram = _get_ram_usage_percent()
    score = _compute_score(ssh, ports, temp, ram)
    history7 = _get_last_days_scores(7)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    recs = _generate_html_recommendations(ssh, ports, temp, ram)
    html = _generate_html_report(score, ssh, ports, temp, ram, ts, recs, history7)
    path = save_html_report(html)
    print(f"[HTML] Informe HTML guardado en: {path}")
    return path

def save_report(text):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, f"security_{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt")
    with open(path, "w") as f:
        f.write(text)
    return path

def cmd_security(json_output=False):
    try:
        ssh = _count_ssh_failures()
        ports = _get_open_ports()
        temp = _get_temperature_c()
        ram = _get_ram_usage_percent()
        score = _compute_score(ssh, ports, temp, ram)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _insert_history(ts, score, ssh, ",".join(ports), temp, ram)
        if json_output:
            data = {"score": int(score), "ssh_failures": int(ssh), "open_ports": ports, "temp_c": temp, "ram_percent": ram, "report_path": None}
            print(json.dumps(data))
            return data
        txt = _format_report(score, ssh, ports, temp, ram)
        path = save_report(txt)
        print(txt)
        print(f"\nInforme guardado en: {path}")
        return {"score": score, "ssh_failures": ssh, "open_ports": ports, "temp_c": temp, "ram_percent": ram, "report_path": path}
    except Exception as e:
        print(f"[ERROR cmd_security]: {e}", file=sys.stderr)
        return {"score": 0, "error": True, "message": str(e)}

def main():
    args = sys.argv[1:]
    html_output = "--html" in args
    json_output = "--json" in args
    if html_output:
        return cmd_html()
    if "--security" in args:
        return cmd_security(json_output=json_output)
    print("Uso: sec-agent --security [--json] [--html]")

if __name__ == "__main__":
    main()
