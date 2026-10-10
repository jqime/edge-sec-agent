#!/usr/bin/env bash
set -euo pipefail

REPO_URL_DEFAULT="https://github.com/jqime/edge-sec-agent.git"
INSTALL_ROOT_DEFAULT="/opt/edge-sec-agent"
SERVICE_USER_DEFAULT="edgesec"
CHANNEL_DEFAULT="stable"

REPO_URL="${EDGE_REPO_URL:-$REPO_URL_DEFAULT}"
INSTALL_ROOT="${EDGE_INSTALL_ROOT:-$INSTALL_ROOT_DEFAULT}"
SERVICE_USER="${EDGE_SERVICE_USER:-$SERVICE_USER_DEFAULT}"
CHANNEL="${EDGE_UPDATE_CHANNEL:-$CHANNEL_DEFAULT}"

usage() {
  cat <<USAGE
Uso: $0 [--repo-url URL] [--channel stable] [--install-root /opt/edge-sec-agent]

Bootstrap idempotente para Debian/DietPi ARM64.
No destruye datos existentes en \$INSTALL_ROOT/data ni \$INSTALL_ROOT/reports.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-url) REPO_URL="$2"; shift 2 ;;
    --channel) CHANNEL="$2"; shift 2 ;;
    --install-root) INSTALL_ROOT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Argumento no soportado: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "Este script requiere root." >&2
  exit 1
fi

ARCH="$(uname -m)"
if [[ "$ARCH" != "aarch64" && "$ARCH" != "arm64" ]]; then
  echo "Arquitectura no soportada: $ARCH (se requiere ARM64)." >&2
  exit 1
fi

if [[ -r /etc/os-release ]]; then
  . /etc/os-release
else
  echo "No se puede detectar el sistema operativo." >&2
  exit 1
fi

if [[ "${ID:-}" != "debian" && "${ID_LIKE:-}" != *debian* ]]; then
  echo "Sistema no soportado: ${PRETTY_NAME:-desconocido} (se requiere Debian/DietPi)." >&2
  exit 1
fi

MEM_KB="$(awk '/MemTotal/{print $2}' /proc/meminfo)"
if [[ -z "$MEM_KB" || "$MEM_KB" -lt 450000 ]]; then
  echo "Memoria insuficiente (< 450MB)." >&2
  exit 1
fi

mkdir -p "$INSTALL_ROOT"
FREE_KB="$(df -Pk "$INSTALL_ROOT" | awk 'NR==2 {print $4}')"
if [[ -z "$FREE_KB" || "$FREE_KB" -lt 2097152 ]]; then
  echo "Espacio insuficiente en $INSTALL_ROOT (< 2GB libres)." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git python3 python3-venv python3-pip curl ca-certificates sqlite3 > /dev/null

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --create-home --home-dir "/home/$SERVICE_USER" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

APP_DIR="$INSTALL_ROOT/app/current"
DATA_DIR="$INSTALL_ROOT/data"
REPORTS_DIR="$INSTALL_ROOT/reports"
BACKUPS_DIR="$INSTALL_ROOT/backups"
CONFIG_DIR="$INSTALL_ROOT/config"
LOG_DIR="$INSTALL_ROOT/logs"

mkdir -p "$DATA_DIR" "$REPORTS_DIR" "$BACKUPS_DIR" "$CONFIG_DIR" "$LOG_DIR" "$(dirname "$APP_DIR")"

if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch --prune origin
  if git -C "$APP_DIR" show-ref --verify --quiet "refs/remotes/origin/$CHANNEL"; then
    git -C "$APP_DIR" checkout "$CHANNEL"
    git -C "$APP_DIR" pull --ff-only origin "$CHANNEL"
  else
    echo "Canal $CHANNEL no encontrado en remoto. Se mantiene rama actual." >&2
  fi
else
  git clone "$REPO_URL" "$APP_DIR"
  if git -C "$APP_DIR" show-ref --verify --quiet "refs/remotes/origin/$CHANNEL"; then
    git -C "$APP_DIR" checkout "$CHANNEL"
  fi
fi

python3 -m venv "$INSTALL_ROOT/app/venv"
"$INSTALL_ROOT/app/venv/bin/pip" install --upgrade pip >/dev/null
"$INSTALL_ROOT/app/venv/bin/pip" install -r "$APP_DIR/requirements.txt" >/dev/null

ENV_FILE="$CONFIG_DIR/edge-sec-agent.env"
if [[ ! -f "$ENV_FILE" ]]; then
  cat > "$ENV_FILE" <<ENV
EDGE_DB_PATH=$DATA_DIR/history.db
REPORTS_DIR=$REPORTS_DIR
EDGE_MODEL=tinyllama:1.1b
EDGE_UPDATE_CHANNEL=$CHANNEL
EDGE_INSTALL_ROOT=$INSTALL_ROOT
ENV
  chmod 640 "$ENV_FILE"
fi

chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_ROOT"
chown root:"$SERVICE_USER" "$ENV_FILE"

install -m 644 "$APP_DIR/systemd/edge-sec-agent.service" /etc/systemd/system/edge-sec-agent.service
install -m 644 "$APP_DIR/systemd/edge-sec-agent-backup.service" /etc/systemd/system/edge-sec-agent-backup.service
install -m 644 "$APP_DIR/systemd/edge-sec-agent-backup.timer" /etc/systemd/system/edge-sec-agent-backup.timer
install -m 644 "$APP_DIR/systemd/edge-sec-agent-health.service" /etc/systemd/system/edge-sec-agent-health.service
install -m 644 "$APP_DIR/systemd/edge-sec-agent-health.timer" /etc/systemd/system/edge-sec-agent-health.timer
install -m 644 "$APP_DIR/systemd/edge-sec-agent-update.service" /etc/systemd/system/edge-sec-agent-update.service
install -m 644 "$APP_DIR/systemd/edge-sec-agent-update.timer" /etc/systemd/system/edge-sec-agent-update.timer

systemd-analyze verify /etc/systemd/system/edge-sec-agent.service
systemctl daemon-reload
systemctl enable edge-sec-agent.service edge-sec-agent-backup.timer edge-sec-agent-health.timer

echo "Bootstrap completado en $INSTALL_ROOT"
echo "Update automático: opt-in creando /etc/edge-sec-agent/update.enabled y habilitando edge-sec-agent-update.timer"
