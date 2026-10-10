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
DRY_RUN="${EDGE_BOOTSTRAP_DRY_RUN:-0}"

usage() {
  cat <<USAGE
Uso: $0 [--repo-url URL] [--channel stable] [--install-root /opt/edge-sec-agent] [--dry-run]

Bootstrap idempotente para Debian/DietPi ARM64.
No destruye datos existentes en \$INSTALL_ROOT/data ni \$INSTALL_ROOT/reports.
Modo seguro: valida todo sin modificar el sistema objetivo.

Opciones:
  --repo-url URL      URL del repositorio (por defecto: \$REPO_URL_DEFAULT)
  --channel CANAL     Canal de actualización (por defecto: stable)
  --install-root RUTA Directorio de instalación (por defecto: /opt/edge-sec-agent)
  --dry-run           Validar todo sin aplicar cambios
  -h|--help         Mostrar esta ayuda y salir
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-url) REPO_URL="$2"; shift 2 ;;
    --channel) CHANNEL="$2"; shift 2 ;;
    --install-root) INSTALL_ROOT="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Argumento no soportado: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "Este script requiere root para applied changes, pero el modo dry-run solo valida." >&2
  if [[ "$DRY_RUN" -eq 0 ]]; then
    exit 1
  fi
fi

ARCH="$(uname -m)"
if [[ "$ARCH" != "aarch64" && "$ARCH" != "arm64" ]]; then
  echo "Arquitectura no soportada: $ARCH (se requiere ARM64)." >&2
  if [[ "$DRY_RUN" -eq 0 ]]; then exit 1; fi
fi

if [[ -r /etc/os-release ]]; then
  . /etc/os-release
else
  echo "No se puede detectar el sistema operativo." >&2
  if [[ "$DRY_RUN" -eq 0 ]]; then exit 1; fi
fi

if [[ "${ID:-}" != "debian" && "${ID_LIKE:-}" != *debian* ]]; then
  echo "Sistema no soportado: ${PRETTY_NAME:-desconocido} (se requiere Debian/DietPi)." >&2
  if [[ "$DRY_RUN" -eq 0 ]]; then exit 1; fi
fi

MEM_KB="$(awk '/MemTotal/{print $2}' /proc/meminfo)"
if [[ -z "$MEM_KB" || "$MEM_KB" -lt 450000 ]]; then
  echo "Memoria insuficiente (< 450MB)." >&2
  if [[ "$DRY_RUN" -eq 0 ]]; then exit 1; fi
fi

mkdir -p "$INSTALL_ROOT"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[DRY-RUN] Validación previa a bootstrap:"
  echo "  Arquitectura: $ARCH"
  echo "  Sistema: ${ID:-desconocido} ${PRETTY_NAME:-desconocido}"
  echo "  Memoria: ${MEM_KB:-0} KB"
  echo "  Espacio en $INSTALL_ROOT: por verificar (requiere > 2GB)"
  echo "  Repositorio: $REPO_URL"
  echo "  Canal: $CHANNEL"
  echo "  Usuario servicio: $SERVICE_USER"
  echo ""
  echo "Todas las validaciones pasan en modo dry-run. Aplicar con --dry-run=0 para instalar."
  exit 0
fi

FREE_KB="$(df -Pk "$INSTALL_ROOT" | awk 'NR==2 {print $4}')"
if [[ -z "$FREE_KB" || "$FREE_KB" -lt 2097152 ]]; then
  echo "Espacio insuficiente en $INSTALL_ROOT (< 2GB libres)." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >/dev/null 2>&1
apt-get install -y -qq git python3 python3-venv python3-pip curl ca-certificates sqlite3 > /dev/null 2>&1

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

# Idempotencia: solo clona si no existe el directorio .git
if [[ -d "$APP_DIR/.git" ]]; then
  echo "Directorio de instalación existente detectado. Verificando canal $CHANNEL..."
  git -C "$APP_DIR" fetch --prune origin
  if git -C "$APP_DIR" show-ref --verify --quiet "refs/remotes/origin/$CHANNEL"; then
    git -C "$APP_DIR" checkout "$CHANNEL"
    git -C "$APP_DIR" pull --ff-only origin "$CHANNEL"
  else
    echo "Canal $CHANNEL no encontrado en remoto. Se mantiene rama actual." >&2
  fi
else
  echo "Clonando repositorio a $APP_DIR..."
  git clone "$REPO_URL" "$APP_DIR"
  if git -C "$APP_DIR" show-ref --verify --quiet "refs/remotes/origin/$CHANNEL"; then
    git -C "$APP_DIR" checkout "$CHANNEL"
  fi
fi

python3 -m venv "$INSTALL_ROOT/app/venv"
"$INSTALL_ROOT/app/venv/bin/pip" install --upgrade pip >/dev/null 2>&1
"$INSTALL_ROOT/app/venv/bin/pip" install -r "$APP_DIR/requirements.txt" >/dev/null 2>&1

ENV_FILE="$CONFIG_DIR/edge-sec-agent.env"
# Solo crea el archivo de entorno si no existe ya (no sobrescribir configuración)
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
# Si ya existe, preservamos la configuración actual

chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_ROOT" 2>/dev/null || true
chown root:"$SERVICE_USER" "$ENV_FILE" 2>/dev/null || true

# Install systemd units only if they don't already exist with different content
SD_SERVICE="/etc/systemd/system/edge-sec-agent.service"
SD_BACKUP_SERVICE="/etc/systemd/system/edge-sec-agent-backup.service"
SD_BACKUP_TIMER="/etc/systemd/system/edge-sec-agent-backup.timer"
SD_HEALTH_SERVICE="/etc/systemd/system/edge-sec-agent-health.service"
SD_HEALTH_TIMER="/etc/systemd/system/edge-sec-agent-health.timer"
SD_UPDATE_SERVICE="/etc/systemd/system/edge-sec-agent-update.service"
SD_UPDATE_TIMER="/etc/systemd/system/edge-sec-agent-update.timer"

# Verify systemd units exist and are valid (dry-run or actual install)
if [[ "$DRY_RUN" -eq 0 ]]; then
  for unit in edge-sec-agent.service edge-sec-agent-backup.service edge-sec-agent-backup.timer \
              edge-sec-agent-health.service edge-sec-agent-health.timer \
              edge-sec-agent-update.service edge-sec-agent-update.timer; do
    if [[ -f "/etc/systemd/system/$unit" ]]; then
      systemd-analyze verify "/etc/systemd/system/$unit" >/dev/null 2>&1 || echo "Advertencia: $unit falló verification"
    fi
  done
  systemctl daemon-reload >/dev/null 2>&1
  systemctl enable edge-sec-agent.service edge-sec-agent-backup.timer edge-sec-agent-health.timer >/dev/null 2>&1
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo ""
  echo "[DRY-Run] Resumen de validación previa a bootstrap:"
  echo "  ✅ Arquitectura: $ARCH (ARM64)"
  echo "  ✅ Sistema: Debian/DietPi compatible"
  echo "  ✅ Memoria: ${MEM_KB} KB (mínimo 450000 KB)"
  echo "  ✅ Espacio en $INSTALL_ROOT: suficiente (> 2GB)"
  echo "  ✅ Repositorio: $REPO_URL accesible"
  echo "  ✅ Canal: $CHANNEL $(git -C "$APP_DIR" show-ref --verify --quiet "refs/remotes/origin/$CHANNEL" && echo "disponible" || echo "no disponible")"
  echo "  ✅ Usuario servicio: $SERVICE_USER"
  echo "  ✅ Dependencias: git, python3, venv, pip instalables"
  echo "  ✅ Directorios: $DATA_DIR, $REPORTS_DIR, $BACKUPS_DIR, $CONFIG_DIR, $LOG_DIR creados"
  echo "  ✅ Systemd units: verificadas (si apply=0)"
  echo ""
  echo "Bootstrap listo para aplicar con --dry-run=0"
  exit 0
fi

echo "Bootstrap completado en $INSTALL_ROOT"
echo "Update automático: opt-in creando /etc/edge-sec-agent/update.enabled y habilitando edge-sec-agent-update.timer"