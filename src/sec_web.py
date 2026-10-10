
"""
sec_web.py — Servidor web Flask para Edge Sec Agent.
Endpoints:
  /v1/global/health   → estado del sistema + métricas de salud
  /metrics            → endpoint estilo Prometheus
  /api/metrics        → JSON completo de seguridad
  /v1/models          → listado de modelos (compatible OpenAI)
  /v1/chat/completions → chat compatible OpenAI
  /ask                → legacy chat
  /                   → dashboard mínimo
"""
import logging
import os
import re
import sqlite3
import subprocess
import threading
import time
from datetime import datetime
from typing import Any
from urllib import error, request as urllib_request

from flask import Flask, Response, g, jsonify, request

from src.agent import (
    _compute_score,
    _count_ssh_failures,
    _get_open_ports,
    _get_ram_usage_percent,
    _get_temperature_c,
)
from src.database import get_latest

logger = logging.getLogger("edge-sec-agent.web")
app = Flask(__name__)
_APP_START_MONOTONIC = time.monotonic()
_stats_lock = threading.Lock()
_stats: dict[str, float] = {
    "requests_total": 0.0,
    "errors_total": 0.0,
    "last_request_latency_seconds": 0.0,
}
_cache_lock = threading.Lock()
_cache: dict[str, tuple[float, dict[str, Any]]] = {}


@app.before_request
def _track_start_time() -> None:
    g.request_start_monotonic = time.monotonic()


@app.after_request
def _track_request_metrics(resp: Response) -> Response:
    elapsed = max(time.monotonic() - getattr(g, "request_start_monotonic", time.monotonic()), 0.0)
    with _stats_lock:
        _stats["requests_total"] += 1
        _stats["last_request_latency_seconds"] = elapsed
        if resp.status_code >= 500:
            _stats["errors_total"] += 1
    return resp


def _cached(name: str, ttl_seconds: int, loader: Any) -> dict[str, Any]:
    now = time.time()
    with _cache_lock:
        hit = _cache.get(name)
        if hit and now - hit[0] < ttl_seconds:
            return hit[1]
    value = loader()
    with _cache_lock:
        _cache[name] = (now, value)
    return value


def _get_uptime_seconds() -> float:
    """Lee segundos desde el boot desde /proc/uptime."""
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except (FileNotFoundError, OSError, ValueError, IndexError) as exc:
        logger.debug("No se pudo leer uptime: %s", exc)
        return 0.0


def _get_fail2ban_banned_ips() -> int:
    """
    Consulta a fail2ban-client el total de IPs baneadas en la jail sshd.
    Devuelve 0 si fail2ban no está disponible.
    """
    try:
        result = subprocess.run(
            ["fail2ban-client", "status", "sshd"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        match = re.search(r"Total banned:\s*(\d+)", result.stdout)
        if match:
            return int(match.group(1))
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as exc:
        logger.debug("fail2ban-client no disponible: %s", exc)
    return 0


def _get_cpu_temp() -> float | None:
    """Lee temperatura CPU desde thermal_zone0."""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except (FileNotFoundError, OSError, ValueError, TypeError) as exc:
        logger.debug("No se pudo leer temperatura CPU: %s", exc)
        return None


def _get_ram_percent() -> float | None:
    """Calcula porcentaje de RAM usado desde /proc/meminfo."""
    try:
        with open("/proc/meminfo") as f:
            total: int | None = None
            avail: int | None = None
            for line in f:
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    avail = int(line.split()[1])
            if total and avail:
                return round(((total - avail) / total) * 100.0, 1)
    except (OSError, ValueError, TypeError) as exc:
        logger.debug("No se pudo leer RAM: %s", exc)
    return None


def _check_ollama() -> dict[str, Any]:
    def _loader() -> dict[str, Any]:
        started = time.monotonic()
        req = urllib_request.Request("http://127.0.0.1:11434/api/tags", method="GET")
        try:
            with urllib_request.urlopen(req, timeout=1.5) as resp:
                return {
                    "ok": resp.status == 200,
                    "latency_ms": round((time.monotonic() - started) * 1000.0, 2),
                }
        except (error.URLError, TimeoutError, OSError):
            return {
                "ok": False,
                "latency_ms": round((time.monotonic() - started) * 1000.0, 2),
            }

    return _cached("ollama", 15, _loader)


def _check_sqlite() -> dict[str, Any]:
    def _loader() -> dict[str, Any]:
        db_path = os.environ.get(
            "EDGE_DB_PATH",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "history.db"),
        )
        if not os.path.exists(db_path):
            return {"ok": True, "detail": "db_not_found"}
        started = time.monotonic()
        try:
            conn = sqlite3.connect(db_path, timeout=2)
            check = conn.execute("PRAGMA quick_check;").fetchone()
            conn.close()
            ok = bool(check and str(check[0]).lower() == "ok")
            return {
                "ok": ok,
                "detail": str(check[0]) if check else "unknown",
                "latency_ms": round((time.monotonic() - started) * 1000.0, 2),
            }
        except sqlite3.Error as exc:
            return {
                "ok": False,
                "detail": str(exc),
                "latency_ms": round((time.monotonic() - started) * 1000.0, 2),
            }

    return _cached("sqlite", 30, _loader)


def _last_update_info() -> dict[str, Any]:
    def _loader() -> dict[str, Any]:
        update_file = os.environ.get("EDGE_LAST_UPDATE_FILE", "/opt/edge-sec-agent/data/last_update.json")
        if not os.path.exists(update_file):
            return {"updated_at": None, "commit": None, "channel": None}
        try:
            import json

            with open(update_file, encoding="utf-8") as f:
                payload = json.load(f)
            return {
                "updated_at": payload.get("updated_at"),
                "commit": payload.get("commit"),
                "channel": payload.get("channel"),
            }
        except (OSError, ValueError, TypeError):
            return {"updated_at": None, "commit": None, "channel": None}

    return _cached("last_update", 15, _loader)


@app.route("/v1/global/health")
def health() -> tuple[Response, int]:
    """
    Endpoint de salud real.
    DEGRADADO si temp >= 70°C o RAM >= 90%.
    Incluye uptime, score de seguridad, IPs baneadas por fail2ban y advertencias.
    """
    temp = _get_cpu_temp()
    ram = _get_ram_percent()
    uptime = _get_uptime_seconds()
    banned = _get_fail2ban_banned_ips()
    latest = get_latest()
    ollama = _check_ollama()
    sqlite_status = _check_sqlite()

    warnings: list[str] = []
    degraded = False

    if temp is not None and temp >= 70:
        warnings.append(f"Temperatura crítica: {temp}°C >= 70°C")
        degraded = True
    elif temp is not None and temp > 55:
        warnings.append(f"Temperatura elevada: {temp}°C")

    if ram is not None and ram >= 90:
        warnings.append(f"RAM crítica: {ram}% >= 90%")
        degraded = True
    elif ram is not None and ram > 75:
        warnings.append(f"RAM elevada: {ram}%")
    if not ollama.get("ok"):
        warnings.append("Ollama no disponible")
        degraded = True
    if not sqlite_status.get("ok"):
        warnings.append("SQLite quick_check falló")
        degraded = True

    status = "DEGRADED" if degraded else "HEALTHY"
    status_code = 503 if degraded else 200

    data: dict[str, Any] = {
        "status": status,
        "device": "Orange Pi Zero 3",
        "environment": "production",
        "uptime_seconds": uptime,
        "security_score": (latest or {}).get("score"),
        "fail2ban_banned_ips": banned,
        "warnings": warnings,
        "hardware": {
            "cpu_temp_c": temp,
            "ram_percent": ram,
        },
        "dependencies": {
            "ollama_ok": bool(ollama.get("ok")),
            "ollama_latency_ms": ollama.get("latency_ms"),
            "sqlite_ok": bool(sqlite_status.get("ok")),
            "sqlite_detail": sqlite_status.get("detail"),
            "sqlite_latency_ms": sqlite_status.get("latency_ms"),
        },
    }
    return jsonify(data), status_code


@app.route("/metrics")
def prometheus_metrics() -> Response:
    """Endpoint Prometheus con temperatura, RAM, score y banned IPs."""
    temp = _get_cpu_temp()
    ram = _get_ram_percent()
    latest = get_latest()
    score = (latest or {}).get("score", 0) or 0
    banned = _get_fail2ban_banned_ips()
    ollama = _check_ollama()
    update = _last_update_info()
    with _stats_lock:
        requests_total = _stats["requests_total"]
        errors_total = _stats["errors_total"]
        last_latency = _stats["last_request_latency_seconds"]
    uptime_seconds = max(time.monotonic() - _APP_START_MONOTONIC, 0.0)
    updated_at = update.get("updated_at")
    updated_epoch = 0
    if updated_at:
        try:
            updated_epoch = int(datetime.fromisoformat(updated_at.replace("Z", "+00:00")).timestamp())
        except ValueError:
            updated_epoch = 0
    commit = os.environ.get("EDGE_GIT_COMMIT", update.get("commit") or "unknown")

    lines = [
        "# HELP edge_sec_cpu_temperature_celsius CPU temperature in Celsius",
        "# TYPE edge_sec_cpu_temperature_celsius gauge",
        f"edge_sec_cpu_temperature_celsius {temp if temp is not None else 0.0}",
        "# HELP edge_sec_ram_used_percentage RAM usage percentage",
        "# TYPE edge_sec_ram_used_percentage gauge",
        f"edge_sec_ram_used_percentage {ram if ram is not None else 0.0}",
        "# HELP edge_sec_security_score Security score 0-100",
        "# TYPE edge_sec_security_score gauge",
        f"edge_sec_security_score {score}",
        "# HELP edge_sec_fail2ban_banned_ips Total banned IPs by Fail2Ban",
        "# TYPE edge_sec_fail2ban_banned_ips gauge",
        f"edge_sec_fail2ban_banned_ips {banned}",
        "# HELP edge_sec_uptime_seconds API process uptime in seconds",
        "# TYPE edge_sec_uptime_seconds gauge",
        f"edge_sec_uptime_seconds {uptime_seconds}",
        "# HELP edge_sec_http_requests_total Total HTTP requests served",
        "# TYPE edge_sec_http_requests_total counter",
        f"edge_sec_http_requests_total {requests_total}",
        "# HELP edge_sec_http_errors_total Total HTTP 5xx responses",
        "# TYPE edge_sec_http_errors_total counter",
        f"edge_sec_http_errors_total {errors_total}",
        "# HELP edge_sec_last_request_latency_seconds Last observed request latency",
        "# TYPE edge_sec_last_request_latency_seconds gauge",
        f"edge_sec_last_request_latency_seconds {last_latency}",
        "# HELP edge_sec_ollama_up Ollama dependency status (1=up, 0=down)",
        "# TYPE edge_sec_ollama_up gauge",
        f"edge_sec_ollama_up {1 if ollama.get('ok') else 0}",
        "# HELP edge_sec_last_update_timestamp Last successful update timestamp (unix)",
        "# TYPE edge_sec_last_update_timestamp gauge",
        f"edge_sec_last_update_timestamp {updated_epoch}",
        "# HELP edge_sec_build_info Build and commit metadata",
        "# TYPE edge_sec_build_info gauge",
        f'edge_sec_build_info{{commit="{commit}"}} 1',
    ]
    return Response("\n".join(lines) + "\n", mimetype="text/plain")


@app.route("/api/metrics")
def api_metrics() -> tuple[Response, int]:
    """
    Devuelve JSON completo de seguridad usando directamente las funciones
    de agent.py (sin lanzar subprocesos).
    """
    try:
        ssh = _count_ssh_failures()
        ports = _get_open_ports()
        temp = _get_temperature_c()
        ram = _get_ram_usage_percent()
        score = _compute_score(ssh, ports, temp, ram)
        return jsonify({
            "score": score,
            "ssh_failures": ssh,
            "open_ports": ports,
            "temp_c": temp,
            "ram_percent": ram,
        }), 200
    except Exception as exc:
        logger.exception("Error en /api/metrics")
        return jsonify({"error": str(exc)}), 500


@app.route("/v1/models")
def list_models() -> tuple[Response, int]:
    """Endpoint compatible OpenAI para listar modelos disponibles."""
    return jsonify({
        "object": "list",
        "data": [{"id": "sec-agent", "object": "model"}],
    }), 200


@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions() -> tuple[Response, int]:
    """Endpoint compatible OpenAI — ejecuta sec-agent --security con el mensaje del usuario."""
    data = request.get_json(silent=True) or {}
    messages = data.get("messages", [])
    pregunta = ""
    for m in messages:
        if m.get("role") == "user":
            pregunta = m.get("content", "")
            break
    if not pregunta:
        pregunta = "estado"
    try:
        result = subprocess.run(
            ["/root/edge-sec-agent/scripts/sec-agent", "--security", pregunta],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        respuesta = result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
        respuesta = "Error ejecutando sec-agent"
    return jsonify({
        "choices": [{"message": {"role": "assistant", "content": respuesta}}],
    }), 200


@app.route("/ask", methods=["POST"])
def ask() -> tuple[Response, int]:
    """Endpoint legacy — ejecuta sec-agent con la pregunta del usuario."""
    data = request.get_json(silent=True) or {}
    pregunta = data.get("pregunta", "")
    try:
        result = subprocess.run(
            ["sec-agent", pregunta],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        respuesta = result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
        respuesta = "Error ejecutando sec-agent"
    return jsonify({"respuesta": respuesta}), 200


@app.route("/")
def index() -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Edge Sec Agent Dashboard</title>"
        "<style>"
        "body{font-family:system-ui,Arial,sans-serif;margin:0;background:#0b1220;color:#e6edf7}"
        ".wrap{max-width:980px;margin:0 auto;padding:1rem}.grid{display:grid;gap:1rem;grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}"
        ".card{background:#121a2b;border:1px solid #24324f;border-radius:12px;padding:1rem}"
        "a{color:#93c5fd}.ok{color:#22c55e}.bad{color:#f87171}.muted{color:#94a3b8}"
        "</style></head><body><div class='wrap'>"
        "<h1>Edge Sec Agent Dashboard</h1>"
        "<p class='muted'>Panel ligero para ARM64. Endpoints API sin cambios.</p>"
        "<div class='grid'>"
        "<div class='card'><h3>Salud</h3><p id='health'>cargando...</p></div>"
        "<div class='card'><h3>Modelo</h3><p id='model'>cargando...</p></div>"
        "<div class='card'><h3>Actualización</h3><p id='update'>cargando...</p></div>"
        "<div class='card'><h3>Enlaces</h3><p><a href='/api/metrics'>/api/metrics</a><br>"
        "<a href='/v1/global/health'>/v1/global/health</a><br>"
        "<a href='/metrics'>/metrics</a><br><a href='/v1/models'>/v1/models</a></p></div></div>"
        "<script>"
        "async function load(){"
        "const h=await fetch('/v1/global/health').then(r=>r.json()).catch(()=>null);"
        "document.getElementById('health').textContent=h?`${h.status} | score=${h.security_score ?? 'n/a'}`:'no disponible';"
        "if(h&&h.dependencies){document.getElementById('model').innerHTML=`Ollama: ${h.dependencies.ollama_ok?'OK':'ERROR'}<br>SQLite: ${h.dependencies.sqlite_ok?'OK':'ERROR'}`;}"
        "const m=await fetch('/metrics').then(r=>r.text()).catch(()=>'' );"
        "const update=(m.match(/edge_sec_last_update_timestamp\\s+(\\d+)/)||[])[1];"
        "document.getElementById('update').textContent=update&&update!=='0'?new Date(parseInt(update,10)*1000).toISOString():'sin datos';"
        "}"
        "load();setInterval(load,30000);"
        "</script></div></body></html>"
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
