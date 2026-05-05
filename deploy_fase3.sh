#!/bin/bash
# Despliegue final en Orange Pi (ejecutar como root)
set -euo pipefail
echo "=== Desplegando Edge Sec Agent Fase 3 ==="

# 1. Instalar Flask si no está
if ! dpkg -l | grep -q python3-flask; then
    apt update && apt install -y python3-flask
fi

# 2. Crear/actualizar sec_web.py
cat > /root/edge-sec-agent/src/sec_web.py << 'EOFWEB'
#!/usr/bin/env python3
from flask import Flask, jsonify
import subprocess, json
app = Flask(__name__)
@app.route("/api/metrics")
def metrics():
    out = subprocess.getoutput("/usr/local/bin/sec-agent --security --json")
    try: return jsonify(json.loads(out))
    except: return jsonify({"error":"no data"}), 500
@app.route("/")
def index():
    return "<html><body><h1>Edge Sec Agent Dashboard</h1><p><a href='/api/metrics'>/api/metrics</a></p></body></html>"
if __name__ == "__main__": app.run(host="0.0.0.0", port=8080)
EOFWEB
# 3. Copiar servicios systemd
cat > /etc/systemd/system/sec-web.service << 'EOFSVC'
[Unit]
Description=Edge Sec Agent Web Dashboard
[Service]
ExecStart=/usr/bin/python3 /root/edge-sec-agent/src/sec_web.py
Restart=always
User=root
[Install]
WantedBy=multi-user.target
EOFSVC
systemctl daemon-reload
systemctl enable --now sec-web

# 4. Copiar scripts a /usr/local/bin
for script in report-cron.sh send_telegram.sh telegram-notify.sh; do
    cp /root/edge-sec-agent/scripts/$script /usr/local/bin/
    chmod +x /usr/local/bin/$script
done
# 5. Asegurar health check
cp /root/edge-sec-agent/health_check.sh /usr/local/bin/
chmod +x /usr/local/bin/health_check.sh

echo "=== Despliegue completado ==="
systemctl status sec-web --no-pager
