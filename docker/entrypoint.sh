#!/bin/bash
set -euo pipefail

SSL_DIR="/etc/nginx/ssl"
HTPASSWD_FILE="/etc/nginx/.htpasswd"
BASIC_AUTH_PASS="${BASIC_AUTH_PASS:-edge_sec_demo}"

# Generar certificado TLS auto-firmado si no existe
if [ ! -f "$SSL_DIR/cert.pem" ] || [ ! -f "$SSL_DIR/key.pem" ]; then
    mkdir -p "$SSL_DIR"
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$SSL_DIR/key.pem" \
        -out "$SSL_DIR/cert.pem" \
        -subj "/C=ES/ST=Madrid/L=Madrid/O=EdgeSecAgent/CN=localhost" 2>/dev/null
    chmod 600 "$SSL_DIR/key.pem"
    echo "TLS certificate generated"
fi

# Generar .htpasswd si no existe
if [ ! -f "$HTPASSWD_FILE" ]; then
    HASH=$(openssl passwd -apr1 "$BASIC_AUTH_PASS" 2>/dev/null)
    echo "admin:${HASH}" > "$HTPASSWD_FILE"
    chmod 640 "$HTPASSWD_FILE"
    echo "Basic Auth credentials created (admin / $BASIC_AUTH_PASS)"
fi

exec nginx -g "daemon off;"
