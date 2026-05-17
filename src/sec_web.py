#!/usr/bin/env python3
from flask import Flask, jsonify, Response
import subprocess, json, os

app = Flask(__name__)

def _get_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except:
        return None

def _get_ram_percent():
    try:
        with open("/proc/meminfo") as f:
            total = avail = None
            for line in f:
                if line.startswith("MemTotal:"): total = int(line.split()[1])
                if line.startswith("MemAvailable:"): avail = int(line.split()[1])
            if total and avail: return round(((total - avail) / total) * 100.0, 1)
    except:
        return None

@app.route("/v1/global/health")
def health():
    status = subprocess.getoutput("sec status 2>/dev/null || echo 'no disponible'")
    temp = _get_cpu_temp()
    return jsonify({
        "status": "HEALTHY",
        "device": "Orange Pi Zero 3",
        "environment": "production",
        "metrics_summary": status,
        "hardware": {"cpu_temp_c": temp}
    })

@app.route("/metrics")
def prometheus_metrics():
    temp = _get_cpu_temp()
    ram = _get_ram_percent()
    lines = []
    lines.append("# HELP edge_sec_cpu_temperature_celsius CPU temperature in Celsius")
    lines.append("# TYPE edge_sec_cpu_temperature_celsius gauge")
    lines.append(f"edge_sec_cpu_temperature_celsius {temp if temp is not None else 0.0}")
    lines.append("# HELP edge_sec_ram_used_percentage RAM usage percentage")
    lines.append("# TYPE edge_sec_ram_used_percentage gauge")
    lines.append(f"edge_sec_ram_used_percentage {ram if ram is not None else 0.0}")
    return Response("\n".join(lines) + "\n", mimetype="text/plain")

@app.route("/api/metrics")
def api_metrics():
    out = subprocess.getoutput("/usr/local/bin/sec-agent --security --json")
    try: return jsonify(json.loads(out))
    except: return jsonify({"error":"no data"}), 500

@app.route("/")
def index():
    return "<html><body><h1>Edge Sec Agent Dashboard</h1><p><a href='/api/metrics'>/api/metrics</a> | <a href='/v1/global/health'>/v1/global/health</a> | <a href='/metrics'>/metrics (Prometheus)</a></p></body></html>"

if __name__ == "__main__": app.run(host="0.0.0.0", port=8080)
