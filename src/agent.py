#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent.py — Módulo principal de recolección y análisis de seguridad.
Obtiene métricas del sistema (SSH, puertos, temperatura, RAM),
calcula un score de seguridad y persiste en base de datos SQLite unificada.
Uso CLI: sec-agent --security [--json] [--html]
"""
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from typing import Any

# Permitir 'from src.xxx' cuando se ejecuta como script directamente
_project_root = os.path.dirname(os.path.dirname(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.database import insert_metric, get_last_days_scores  # noqa: E402

logger = logging.getLogger("edge-sec-agent.agent")

MODEL = os.environ.get("EDGE_MODEL", "tinyllama:1.1b")
MAX_TOKENS = int(os.environ.get("EDGE_MAX_TOKENS", "120"))
HTTP_TIMEOUT = int(os.environ.get("EDGE_TIMEOUT", "180"))
REPORTS_DIR = os.environ.get("REPORTS_DIR", "/root/edge-sec-agent/reports")

SECRETS_PATH = "/root/edge-sec-agent/secrets.env"
if os.path.exists(SECRETS_PATH):
    _key_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
    try:
        with open(SECRETS_PATH, encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if not _line or _line.startswith("#"):
                    continue
                if "=" not in _line:
                    logger.warning("Línea inválida ignorada en secrets.env: %s", _line[:40])
                    continue
                _key, _val = _line.split("=", 1)
                _key = _key.strip()
                _val = _val.strip().strip('"').strip("'")
                if not _key_re.match(_key):
                    logger.warning("Clave insegura ignorada en secrets.env: %s", _key)
                    continue
                os.environ.setdefault(_key, _val)
    except OSError as _exc:
        logger.error("No se pudo leer secrets.env: %s", _exc)


def _run_command(cmd: str, timeout: int = 10) -> str:
    """Ejecuta un comando shell y devuelve stdout+stderr, o '-' en error."""
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.stdout.strip() or r.stderr.strip() or "-"
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("Comando falló (timeout=%s): %s — %s", timeout, cmd[:60], exc)
        return "-"


def get_ctx() -> dict[str, str]:
    """Devuelve un resumen rápido del contexto del sistema (uso externo/MCP)."""
    temp_raw = _run_command("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
    try:
        temp = f"{int(temp_raw) / 1000:.1f}C"
    except (ValueError, TypeError):
        temp = "?"
    ports = _run_command(
        "ss -tlnp 2>/dev/null | awk 'NR>1{print $4}' "
        "| rev | cut -d: -f1 | rev | sort -n | uniq | tr '\\n' ' '"
    )
    ip = _run_command("hostname -I").split()[0] if _run_command("hostname -I") != "-" else "?"
    ram = _run_command("free -h | awk '/Mem/{print $3\"/\"$2}'")
    failed = _run_command("lastb 2>/dev/null | wc -l")
    return {
        "ip": ip,
        "ram": ram,
        "temp": temp,
        "ports": ports.strip() or "ninguno",
        "failed": failed.strip(),
    }


def _count_ssh_failures() -> int:
    """
    Cuenta fallos de autenticación SSH leyendo logs del sistema.
    Busca 'Failed password' y 'authentication failure' en auth.log/secure.
    """
    paths = os.environ.get("SSH_LOG_PATHS", "/var/log/auth.log,/var/log/secure").split(",")
    total = 0
    for p in paths:
        if not os.path.exists(p):
            continue
        try:
            with open(p, "r", errors="ignore") as f:
                for line in f:
                    if "Failed password" in line or "authentication failure" in line.lower():
                        total += 1
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("No se pudo leer %s: %s", p, exc)
    return total


def _get_open_ports() -> list[str]:
    """
    Escanea puertos TCP en estado LISTEN usando ss, netstat o /proc/net/tcp.
    Devuelve lista ordenada de puertos como strings.
    """
    ports: set[str] = set()
    for cmd in ["ss -tlnp 2>/dev/null", "netstat -tlnp 2>/dev/null"]:
        try:
            out = _run_command(cmd)
            if out and out.strip() != "-":
                for line in out.splitlines():
                    if "LISTEN" in line:
                        for token in line.split():
                            if ":" in token:
                                port = token.split(":")[-1]
                                if port.isdigit():
                                    ports.add(port)
                if ports:
                    return sorted(ports, key=int)
        except (ValueError, TypeError) as exc:
            logger.debug("Error parseando puertos desde %s: %s", cmd[:30], exc)
    try:
        with open("/proc/net/tcp", "r") as f:
            for line in f.readlines()[1:]:
                fields = line.strip().split()
                if len(fields) >= 2:
                    port_hex = fields[1].split(":")[-1]
                    try:
                        ports.add(str(int(port_hex, 16)))
                    except (ValueError, IndexError):
                        continue
        return sorted(ports, key=int)
    except OSError as exc:
        logger.warning("No se pudo leer /proc/net/tcp: %s", exc)
        return []


def _get_temperature_c() -> float | None:
    """Lee la temperatura de la CPU desde /sys/class/thermal/thermal_zone{N}/temp."""
    for i in range(10):
        path = f"/sys/class/thermal/thermal_zone{i}/temp"
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r") as f:
                return int(f.read().strip()) / 1000.0
        except (OSError, ValueError, TypeError):
            continue
    logger.debug("No se encontró sensor de temperatura en thermal_zone0-9")
    return None


def _get_ram_usage_percent() -> float | None:
    """
    Calcula el porcentaje de RAM usado desde /proc/meminfo.
    Fórmula: ((MemTotal - MemAvailable) / MemTotal) * 100
    """
    try:
        with open("/proc/meminfo", "r") as f:
            total: int | None = None
            avail: int | None = None
            for line in f:
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    avail = int(line.split()[1])
            if total and avail:
                return ((total - avail) / total) * 100.0
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("Error leyendo /proc/meminfo: %s", exc)
    return None


# Penalizaciones de _compute_score:
#   SSH:   2 pts por fallo, tope 60  — indica fuerza bruta activa
#   Puertos de riesgo: 8 pts cada uno, tope 40  — puertos no esenciales abiertos
#   Temperatura >55°C: 1.5 pts por grado extra, tope 25  — sobrecalentamiento = throttling
#   RAM >60%: 0.8 pts por punto extra, tope 25  — presión de memoria = riesgo de OOM
def _compute_score(
    ssh: int, ports: list[str], temp: float | None, ram: float | None
) -> int:
    penalties = float(min(ssh * 2, 60))
    allowed = {22, 80, 443, 25, 53}
    risk_ports = sum(1 for p in ports if int(p) not in allowed)
    penalties += float(min(risk_ports * 8, 40))
    if temp is not None and temp > 55:
        penalties += min((temp - 55) * 1.5, 25)
    if ram is not None and ram > 60:
        penalties += min((ram - 60) * 0.8, 25)
    return max(0, 100 - int(penalties))


def _format_report(
    score: int, ssh: int, ports: list[str], temp: float | None, ram: float | None
) -> str:
    lines = [
        f"Informe de Seguridad - Puntuación: {score}/100",
        "Riesgos detectados:",
    ]
    lines.append(f"- SSH fallos: {ssh}")
    lines.append(f"- Puertos abiertos: {', '.join(ports) if ports else 'ninguno'}")
    lines.append(f"- Temperatura CPU: {temp:.1f}C" if temp is not None else "- Temperatura: desconocida")
    lines.append(f"- RAM usado: {ram:.1f}%" if ram is not None else "- RAM: desconocido")
    lines.append("\nRecomendaciones:")
    if ssh > 0:
        lines.append("  \u2022 SSH: deshabilitar login por contrase\u00f1a, usar claves, fail2ban.")
    if ports:
        lines.append("  \u2022 Puertos: cerrar servicios no esenciales, usar firewall.")
    if temp is not None and temp > 55:
        lines.append("  \u2022 Temperatura: mejorar refrigeraci\u00f3n, reducir carga.")
    if ram is not None and ram > 60:
        lines.append("  \u2022 RAM: optimizar procesos, a\u00f1adir swap.")
    if not (ssh or ports or (temp is not None and temp > 55) or (ram is not None and ram > 60)):
        lines.append("  \u2022 Sistema estable. Mant\u00e9n monitorizaci\u00f3n.")
    return "\n".join(lines)


def _format_html_report(
    score: int,
    ssh: int,
    ports: list[str],
    temp: float | None,
    ram: float | None,
    ts: str | None = None,
    recs: list[str] | None = None,
    history7: list[dict[str, Any]] | None = None,
) -> str:
    ts = ts or time.strftime("%Y-%m-%d %H:%M:%S")
    ports_str = ", ".join(ports) if ports else "ninguno"
    temp_str = f"{temp:.1f}C" if isinstance(temp, (int, float)) else "desconocida"
    ram_str = f"{ram:.1f}%" if isinstance(ram, (int, float)) else "desconocido"
    rec_html = ""
    if recs:
        items = "".join(f"<li>{r}</li>" for r in recs)
        rec_html = f"<h3>Recomendaciones</h3><ul>{items}</ul>"
    history7_js = "[]"
    history7_html = ""
    if history7:
        history7_js = json.dumps(history7)
        history7_html = f"""
        <div style="margin-top:20px;"><canvas id="scoreChart" width="800" height="240"></canvas></div>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>const chartData = {history7_js}; const labels = chartData.map(d=>d.date); const data = chartData.map(d=>d.score); new Chart(document.getElementById('scoreChart'),{{type:'line',data:{{labels:labels,datasets:[{{label:'Score',data:data,borderColor:'rgb(75,192,192)',fill:false}}]}},options:{{responsive:true,scales:{{y:{{beginAtZero:true,max:100}}}}}}}})</script>
        """
    score_class = "green" if score >= 70 else ("orange" if score >= 50 else "red")
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Seguridad - {ts}</title><style>
:root{{--bg:#f7f7f7;--card:#fff;--text:#333;--muted:#555;--green:#28a745;--orange:#ff9800;--red:#e74c3c}}
body{{font-family:Arial;background:var(--bg);color:var(--text);margin:0;padding:0}}
.container{{max-width:1100px;margin:40px auto;padding:20px;background:var(--card);border-radius:8px}}
h1{{text-align:center;color:#2a6bd6}}
table{{width:100%;border-collapse:collapse;margin-top:20px}}
th,td{{border:1px solid #ddd;padding:12px;text-align:left}}
th{{background:#f0f0f0}}
.score-row td{{font-weight:bold;font-size:1.1em}}
@media(max-width:900px){{.container{{margin:20px}}}}
</style></head><body><div class="container"><h1>Informe de Seguridad</h1><div class="meta" style="text-align:center;color:var(--muted)">Fecha/hora: {ts}</div><div style="text-align:center"><span class="score-row"><span class="score {score_class}">Puntuaci\u00f3n: {score}/100</span></span></div>
<table><tr><th>M\u00e9trica</th><th>Valor</th></tr><tr><td>SSH fallos</td><td>{ssh}</td></tr><tr><td>Puertos abiertos</td><td>{ports_str}</td></tr><tr><td>Temperatura CPU</td><td>{temp_str}</td></tr><tr><td>RAM usado</td><td>{ram_str}</td></tr></table>{rec_html}{history7_html}</div></body></html>"""
    return html


def _generate_html_recommendations(
    ssh: int, ports: list[str], temp: float | None, ram: float | None
) -> list[str]:
    recs: list[str] = []
    if ssh > 0:
        recs.append("SSH: usar autenticación por clave, deshabilitar root y login por contraseña, activar fail2ban.")
    if ports:
        recs.append("Puertos abiertos: cerrar servicios no esenciales, usar firewall.")
    if temp is not None and temp > 55:
        recs.append("Temperatura alta: mejorar refrigeración.")
    if ram is not None and ram > 60:
        recs.append("RAM alta: optimizar procesos, añadir swap.")
    if not recs:
        recs.append("Sistema estable. Mantén monitorización.")
    return recs


def save_html_report(html_text: str) -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, f"security_{datetime.now().strftime('%Y%m%d-%H%M%S')}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_text)
    logger.info("Informe HTML guardado: %s", path)
    return path


def save_report(text: str) -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, f"security_{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt")
    with open(path, "w") as f:
        f.write(text)
    logger.info("Informe TXT guardado: %s", path)
    return path


def cmd_html() -> str:
    """Genera y guarda un informe HTML con gráfico de 7 días."""
    ssh = _count_ssh_failures()
    ports = _get_open_ports()
    temp = _get_temperature_c()
    ram = _get_ram_usage_percent()
    score = _compute_score(ssh, ports, temp, ram)
    history7 = get_last_days_scores(7)
    recs = _generate_html_recommendations(ssh, ports, temp, ram)
    html = _format_html_report(score, ssh, ports, temp, ram, recs=recs, history7=history7)
    path = save_html_report(html)
    print(f"[HTML] Informe HTML guardado en: {path}")
    return path


def cmd_security(json_output: bool = False) -> dict[str, Any]:
    """
    Ejecuta el análisis de seguridad completo: recolecta métricas,
    calcula score, persiste en BD y opcionalmente imprime JSON.
    """
    try:
        ssh = _count_ssh_failures()
        ports = _get_open_ports()
        temp = _get_temperature_c()
        ram = _get_ram_usage_percent()
        score = _compute_score(ssh, ports, temp, ram)

        insert_metric(
            score=score,
            ssh_failures=ssh,
            open_ports=",".join(ports),
            cpu_temp=temp,
            ram_percent=ram,
        )

        if json_output:
            result = {
                "score": score,
                "ssh_failures": ssh,
                "open_ports": ports,
                "temp_c": temp,
                "ram_percent": ram,
                "report_path": None,
            }
            print(json.dumps(result))
            return result

        txt = _format_report(score, ssh, ports, temp, ram)
        path = save_report(txt)
        print(txt)
        print(f"\nInforme guardado en: {path}")
        return {
            "score": score,
            "ssh_failures": ssh,
            "open_ports": ports,
            "temp_c": temp,
            "ram_percent": ram,
            "report_path": path,
        }
    except (OSError, ValueError, TypeError) as exc:
        logger.error("Error en cmd_security: %s", exc, exc_info=True)
        print(f"[ERROR] {exc}", file=sys.stderr)
        return {"score": 0, "error": True, "message": str(exc)}


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    args = sys.argv[1:]
    if "--html" in args:
        cmd_html()
    elif "--security" in args:
        cmd_security(json_output="--json" in args)
    else:
        print("Uso: sec-agent --security [--json] [--html]")


if __name__ == "__main__":
    main()
