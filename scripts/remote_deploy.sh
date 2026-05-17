#!/bin/bash
set -euo pipefail

REPO_DIR="/root/edge-sec-agent"
NGINX_CONF_SRC="$REPO_DIR/nginx_agent.conf"
NGINX_CONF_DST="/etc/nginx/sites-enabled/edge-sec-agent.conf"
NGINX_CONF_AVAIL="/etc/nginx/sites-available/edge-sec-agent.conf"

echo "=== Edge Sec Agent - Remote Deploy ==="

# 1. Actualizar código desde Git
echo "[1/7] Pulling latest changes from Git..."
cd "$REPO_DIR"
git pull --rebase --autostash

# 2. Instalar dependencias del sistema
echo "[2/7] Installing nginx and gunicorn..."
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
echo "[3/7] Configuring nginx reverse proxy..."
cp "$NGINX_CONF_SRC" "$NGINX_CONF_AVAIL"
ln -sf "$NGINX_CONF_AVAIL" "$NGINX_CONF_DST"

# Eliminar default site si existe para evitar conflictos de puerto
rm -f /etc/nginx/sites-enabled/default

nginx -t > /dev/null 2>&1 && systemctl reload nginx || systemctl restart nginx

# 4. Detener servidor de desarrollo Flask anterior e instalar servicio systemd
echo "[4/7] Stopping old Flask dev server and installing systemd service..."
pkill -f "python.*sec_web.py" 2>/dev/null || true
pkill -f "gunicorn.*wsgi:app" 2>/dev/null || true
sleep 1

# Instalar servicio systemd para Gunicorn
cp "$REPO_DIR/edge-sec-agent.service" /etc/systemd/system/edge-sec-agent.service
systemctl daemon-reload
systemctl enable edge-sec-agent
systemctl restart edge-sec-agent
sleep 2

# 5. Verificar Gunicorn via systemd y endpoints
echo "[5/7] Verifying Gunicorn service and endpoints..."
if systemctl is-active --quiet edge-sec-agent; then
    echo "    edge-sec-agent.service: ACTIVE"
else
    echo "    edge-sec-agent.service: FAILED - check journalctl -u edge-sec-agent"
    exit 1
fi

if curl -sf http://127.0.0.1:5000/ > /dev/null; then
    echo "    Flask app (Gunicorn): HEALTHY"
else
    echo "    Flask app (Gunicorn): UNREACHABLE"
fi

if curl -sf http://127.0.0.1:8080/ > /dev/null; then
    echo "    Nginx proxy: HEALTHY (port 8080)"
else
    echo "    Nginx proxy: UNREACHABLE - check nginx config"
fi

echo "=== Deploy complete ==="

# 6. Hardening Dropbear SSH: forzar puerto 2222 y bloquear 22
echo "[6/7] Hardening Dropbear SSH..."
DROPBEAR_CONF="/etc/default/dropbear"
if [ -f "$DROPBEAR_CONF" ]; then
    # Guardar backup de la configuración original
    cp "$DROPBEAR_CONF" "${DROPBEAR_CONF}.bak.$(date +%Y%m%d%H%M%S)"

    # Forzar puerto 2222 y eliminar cualquier -p 22 o puerto duplicado
    sed -i 's/^DROPBEAR_PORT=.*/DROPBEAR_PORT=2222/' "$DROPBEAR_CONF"
    sed -i 's/^DROPBEAR_EXTRA_OPTS=.*/DROPBEAR_EXTRA_OPTS="-p 2222"/' "$DROPBEAR_CONF"

    # Si no existían las variables, añadirlas
    grep -q '^DROPBEAR_PORT=' "$DROPBEAR_CONF" || echo 'DROPBEAR_PORT=2222' >> "$DROPBEAR_CONF"
    grep -q '^DROPBEAR_EXTRA_OPTS=' "$DROPBEAR_CONF" || echo 'DROPBEAR_EXTRA_OPTS="-p 2222"' >> "$DROPBEAR_CONF"

    # Reiniciar dropbear de forma segura (no rompe sesión SSH activa)
    systemctl restart dropbear 2>/dev/null || service dropbear restart 2>/dev/null || true
    sleep 2

    # Verificar que dropbear solo escucha en 2222
    if ss -tlnp | grep -q ':2222\b'; then
        echo "    Dropbear: LISTENING on port 2222"
    else
        echo "    Dropbear: WARNING - verify manually"
    fi

    if ss -tlnp | grep -q ':22\b'; then
        echo "    Dropbear: WARNING - still listening on port 22"
    else
        echo "    Dropbear: port 22 disabled"
    fi
else
    echo "    Dropbear config not found at $DROPBEAR_CONF - skipping"
fi

# 7. Bloquear tráfico entrante residual al puerto 22 con iptables
echo "[7/7] Blocking residual port 22 traffic with iptables..."
# No bloquear si la sesión SSH actual usa puerto 22 (evitar lockout)
CURRENT_SSH_PORT=$(echo "$SSH_CONNECTION" | awk '{print $4}' || echo "")
if [ "$CURRENT_SSH_PORT" = "22" ]; then
    echo "    WARNING: Current SSH session uses port 22. Skipping iptables DROP rule to avoid lockout."
    echo "    Migrate your session to port 2222 first: ssh -p 2222 root@<IP>"
else
    # Regla para IPv4
    iptables -C INPUT -p tcp --dport 22 -j DROP 2>/dev/null || iptables -I INPUT -p tcp --dport 22 -j DROP
    # Regla para IPv6
    ip6tables -C INPUT -p tcp --dport 22 -j DROP 2>/dev/null || ip6tables -I INPUT -p tcp --dport 22 -j DROP
    echo "    iptables: port 22 blocked (IPv4 + IPv6)"
fi

echo "=== Deploy & Hardening complete ==="
