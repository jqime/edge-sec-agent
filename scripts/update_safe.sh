#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="${EDGE_INSTALL_ROOT:-/opt/edge-sec-agent}"
APP_DIR="${EDGE_APP_DIR:-$INSTALL_ROOT/app/current}"
LOCK_FILE="${EDGE_UPDATE_LOCK_FILE:-$INSTALL_ROOT/update.lock}"
SERVICE_NAME="${EDGE_SERVICE_NAME:-edge-sec-agent}"
CHANNEL="${EDGE_UPDATE_CHANNEL:-stable}"
HEALTH_URL="${EDGE_HEALTH_URL:-http://127.0.0.1:5000/v1/global/health}"
TIMEOUT_SEC="${EDGE_UPDATE_TIMEOUT_SEC:-900}"
DRY_RUN=0
git_safe() {
  git -c "safe.directory=$APP_DIR" -C "$APP_DIR" "$@"
}

usage() {
  echo "Uso: $0 [--dry-run] [--channel stable]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --channel) CHANNEL="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Argumento no soportado: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ "$CHANNEL" == "main" || "$CHANNEL" == "master" ]]; then
  if [[ "${EDGE_ALLOW_MAIN_UPDATE:-0}" != "1" ]]; then
    echo "Actualización de $CHANNEL bloqueada por seguridad. Usa EDGE_ALLOW_MAIN_UPDATE=1 explícitamente." >&2
    exit 1
  fi
fi

if [[ ! -d "$APP_DIR/.git" ]]; then
  echo "No hay repo Git en $APP_DIR" >&2
  exit 1
fi

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "Ya hay una actualización en curso." >&2
  exit 1
fi

run_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[DRY-RUN] $*"
  else
    "$@"
  fi
}

if [[ -n "$(git_safe status --porcelain)" ]]; then
  echo "Repositorio con cambios locales. Abortando actualización segura." >&2
  exit 1
fi

OLD_SHA="$(git_safe rev-parse HEAD)"

run_cmd git_safe fetch --prune origin
if ! git_safe show-ref --verify --quiet "refs/remotes/origin/$CHANNEL"; then
  echo "Canal remoto origin/$CHANNEL no existe." >&2
  exit 1
fi

run_cmd git_safe checkout "$CHANNEL"
run_cmd git_safe reset --hard "origin/$CHANNEL"

run_cmd "$APP_DIR/scripts/backup_state.sh"

if [[ "$DRY_RUN" -eq 0 ]]; then
  timeout "$TIMEOUT_SEC" python3 -m compileall "$APP_DIR/src"
  VENV_DIR="$INSTALL_ROOT/app/venv"
  if [[ ! -x "$VENV_DIR/bin/ruff" || ! -x "$VENV_DIR/bin/mypy" || ! -x "$VENV_DIR/bin/pytest" ]]; then
    echo "Entorno de validación incompleto: $VENV_DIR" >&2
    git_safe reset --hard "$OLD_SHA" >/dev/null 2>&1
    exit 1
  fi
  timeout "$TIMEOUT_SEC" "$VENV_DIR/bin/ruff" check "$APP_DIR/src" "$APP_DIR/tests"
  timeout "$TIMEOUT_SEC" "$VENV_DIR/bin/mypy" "$APP_DIR/src" --ignore-missing-imports
  timeout "$TIMEOUT_SEC" "$VENV_DIR/bin/pytest" "$APP_DIR/tests" -q
fi

run_cmd systemctl restart "$SERVICE_NAME"

if [[ "$DRY_RUN" -eq 0 ]]; then
  if ! curl --fail --silent --show-error --max-time 10 "$HEALTH_URL" >/dev/null; then
    echo "Health check post-update falló. Iniciando rollback a $OLD_SHA..." >&2
    git_safe reset --hard "$OLD_SHA" >/dev/null 2>&1
    run_cmd systemctl restart "$SERVICE_NAME" >/dev/null 2>&1
    sleep 2
    if curl --fail --silent --show-error --max-time 10 "$HEALTH_URL" >/dev/null; then
      echo "Rollback completado: health check exitoso tras restauración a $OLD_SHA" >&2
    else
      echo "Rollback verificado: health check continúa fallando tras restauración a $OLD_SHA" >&2
    fi
    exit 1
  fi
fi

if [[ "$DRY_RUN" -eq 0 ]]; then
  mkdir -p "$INSTALL_ROOT/data"
  printf '{"updated_at":"%s","channel":"%s","commit":"%s"}\n' "$(date -u +%FT%TZ)" "$CHANNEL" "$(git_safe rev-parse HEAD)" > "$INSTALL_ROOT/data/last_update.json"
fi

echo "Update seguro completado (canal=$CHANNEL, dry_run=$DRY_RUN)"
