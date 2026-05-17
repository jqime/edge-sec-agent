#!/bin/bash
set -euo pipefail

REPO_DIR="/root/edge-sec-agent"
NGINX_CONF_SRC="$REPO_DIR/nginx_agent.conf"
NGINX_CONF_DST="/etc/nginx/sites-enabled/edge-sec-agent.conf"
NGINX_CONF_AVAIL="/etc/nginx/sites-available/edge-sec-agent.conf"

echo "=== Edge Sec Agent - Remote Deploy ==="

# 1. Actualizar código desde Git
echo "[1/6] Pulling latest changes from Git..."
cd "$REPO_DIR"
git pull --rebase --autostash

# 2. Instalar dependencias del sistema
echo "[2/6] Installing nginx and gunicorn..."
apt-get update -qq
apt-get install -y -qq nginx python3-pip python3-venv > /dev/null 2>&1 || true

# Crear entorno virtual si no existe
if [ ! -d "$REPO_DIR/venv" ]; then
    echo "    Creating Python virtual environment..."
    python3 -m venv "$REPO_DIR/venv"
fi

source "$REPO_DIR/venv/bin/activate"
pip install -q flask gunicorn

# 3. Configurar nginx
echo "[3/6] Configuring nginx reverse proxy..."
cp "$NGINX_CONF_SRC" "$NGINX_CONF_AVAIL"
ln -sf "$NGINX_CONF_AVAIL" "$NGINX_CONF_DST"

# Eliminar default site si existe para evitar conflictos de puerto
rm -f /etc/nginx/sites-enabled/default

nginx -t > /dev/null 2>&1 && systemctl reload nginx || systemctl restart nginx

# 4. Detener servidor de desarrollo Flask anterior
echo "[4/6] Stopping old Flask dev server..."
pkill -f "python.*sec_web.py" 2>/dev/null || true
pkill -f "python.*wsgi.py" 2>/dev/null || true
sleep 1

# 5. Levantar Gunicorn en modo daemon
echo "[5/6] Starting Gunicorn on 127.0.0.1:5000..."
cd "$REPO_DIR"
source "$REPO_DIR/venv/bin/activate"
gunicorn --daemon \
    --bind 127.0.0.1:5000 \
    --workers 2 \
    --timeout 120 \
    --access-logfile /var/log/gunicorn-edge-access.log \
    --error-logfile /var/log/gunicorn-edge-error.log \
    wsgi:app

sleep 2

# 6. Verificar servicios
echo "[6/6] Verifying deployment..."
if pgrep -x gunicorn > /dev/null; then
    echo "    Gunicorn: RUNNING (PID: $(pgrep -x gunicorn | head -1))"
else
    echo "    Gunicorn: FAILED - check /var/log/gunicorn-edge-error.log"
    exit 1
fi

if curl -sf http://127.0.0.1:5000/ > /dev/null; then
    echo "    Flask app: HEALTHY"
else
    echo "    Flask app: UNREACHABLE"
fi

if curl -sf http://127.0.0.1:8080/ > /dev/null; then
    echo "    Nginx proxy: HEALTHY (port 8080)"
else
    echo "    Nginx proxy: UNREACHABLE - check nginx config"
fi

echo "=== Deploy complete ==="
