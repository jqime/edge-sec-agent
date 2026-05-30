#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
import re
import subprocess
from typing import Any

from flask import Flask, jsonify, Response, request

from src.agent import (
    _count_ssh_failures,
    _get_open_ports,
    _get_temperature_c,
    _get_ram_usage_percent,
    _compute_score,
)
from src.database import get_latest

logger = logging.getLogger("edge-sec-agent.web")
app = Flask(__name__)


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
        )
        match = re.search(r"Total banned:\s*(\d+)", result.stdout)
        if match:
            return int(match.group(1))
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
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
        logger.error("Error en /api/metrics: %s", exc, exc_info=True)
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
    """Endpoint compatible OpenAI — ejecuta sec-agent con el mensaje del usuario."""
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
            ["sec-agent", pregunta],
            capture_output=True,
            text=True,
            timeout=30,
        )
        respuesta = result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
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
        )
        respuesta = result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        respuesta = "Error ejecutando sec-agent"
    return jsonify({"respuesta": respuesta}), 200


@app.route("/")
def index() -> str:
    return (
        "<html><body>"
        "<h1>Edge Sec Agent Dashboard</h1>"
        "<p><a href='/api/metrics'>/api/metrics</a> | "
        "<a href='/v1/global/health'>/v1/global/health</a> | "
        "<a href='/metrics'>/metrics (Prometheus)</a> | "
        "<a href='/v1/models'>/v1/models</a></p>"
        "</body></html>"
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
