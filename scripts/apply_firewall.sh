#!/usr/bin/env bash
# apply_firewall.sh — Hardening de firewall idempotente (IPv4 + IPv6) para
# Edge Sec Agent.
#
# Características:
#   - Idempotente: usa 'iptables -C ... || iptables -A ...' (nunca -I).
#   - NO hace flush de la tabla filter.
#   - NO toca las cadenas gestionadas por Tailscale (ts-input / ts-forward);
#     solo añade reglas al final de la cadena INPUT.
#   - Guard: aborta si la interfaz de Tailscale no existe (evita lockout).
#
# Uso:
#   apply_firewall.sh [--dry-run] [--remove]
#     --dry-run   Muestra las acciones sin modificar el firewall.
#     --remove    Elimina las reglas custom (rollback).
#
set -euo pipefail

IPTABLES="${IPTABLES:-iptables}"
IP6TABLES="${IP6TABLES:-ip6tables}"
TS_IFACE="${EDGE_TS_IFACE:-tailscale0}"

DRY_RUN=0
REMOVE=0

usage() {
  sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
}

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --remove)  REMOVE=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Argumento no reconocido: $arg" >&2; exit 2 ;;
  esac
done

log() { printf '[apply_firewall] %s\n' "$*"; }
die() { printf '[apply_firewall][ERROR] %s\n' "$*" >&2; exit 1; }

require_bin() {
  command -v "$1" >/dev/null 2>&1 || die "binario requerido no encontrado: $1"
}

# Ejecuta un comando, o solo lo muestra si estamos en --dry-run.
run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    log "DRY-RUN: $*"
  else
    "$@"
  fi
}

# Añade la regla si no existe (idempotente).
ensure_rule() {
  local bin="$1"; shift
  if "$bin" -C INPUT "$@" 2>/dev/null; then
    log "ya presente: $bin -A INPUT $*"
  else
    run "$bin" -A INPUT "$@"
    log "añadida:    $bin -A INPUT $*"
  fi
  return 0
}

# Elimina todas las copias de la regla (rollback idempotente).
remove_rule() {
  local bin="$1"; shift
  while "$bin" -C INPUT "$@" 2>/dev/null; do
    run "$bin" -D INPUT "$@"
    log "eliminada:  $bin -D INPUT $*"
    # En dry-run la regla sigue existiendo; cortamos para no iterar sin fin.
    if [ "$DRY_RUN" -eq 1 ]; then
      break
    fi
  done
  return 0
}

# Aplica/elimina un bloque de reglas (una por línea) para una familia.
process_family() {
  local bin="$1" rules_text="$2" mode="$3"
  local line
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    read -r -a toks <<<"$line"
    if [ "$mode" = "apply" ]; then
      ensure_rule "$bin" "${toks[@]}"
    else
      remove_rule "$bin" "${toks[@]}"
    fi
  done <<<"$rules_text"
  return 0
}

wait_for_iface() {
  local i
  for i in $(seq 1 15); do
    if ip link show "$TS_IFACE" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

require_bin "$IPTABLES"
require_bin "$IP6TABLES"

# Guard anti-lockout: al aplicar, la interfaz de Tailscale debe existir.
if [ "$REMOVE" -eq 0 ]; then
  if ! ip link show "$TS_IFACE" >/dev/null 2>&1 && ! wait_for_iface; then
    die "interfaz '$TS_IFACE' no encontrada; abortando para evitar lockout"
  fi
fi

RULES_V4="
-p tcp -s 127.0.0.1 --dport 5000 -j ACCEPT
-p tcp --dport 5000 -j DROP
-p tcp -s 127.0.0.1 --dport 11434 -j ACCEPT
-p tcp --dport 11434 -j DROP
-i ${TS_IFACE} -p tcp --dport 2222 -j ACCEPT
-p tcp --dport 2222 -j DROP
-i ${TS_IFACE} -p tcp --dport 2223 -j ACCEPT
-p tcp --dport 2223 -j DROP
-p tcp --dport 22 -j DROP
"

RULES_V6="
-p tcp -s ::1 --dport 5000 -j ACCEPT
-p tcp --dport 5000 -j DROP
-p tcp -s ::1 --dport 11434 -j ACCEPT
-p tcp --dport 11434 -j DROP
-i ${TS_IFACE} -p tcp --dport 2222 -j ACCEPT
-p tcp --dport 2222 -j DROP
-i ${TS_IFACE} -p tcp --dport 2223 -j ACCEPT
-p tcp --dport 2223 -j DROP
-p tcp --dport 22 -j DROP
"

if [ "$REMOVE" -eq 1 ]; then
  log "modo: REMOVE (rollback)"
  process_family "$IP6TABLES" "$RULES_V6" remove
  process_family "$IPTABLES" "$RULES_V4" remove
else
  log "modo: APPLY (idempotente)"
  process_family "$IPTABLES" "$RULES_V4" apply
  process_family "$IP6TABLES" "$RULES_V6" apply
fi

if [ "$DRY_RUN" -eq 0 ]; then
  log "reglas IPv4 (INPUT):"
  "$IPTABLES" -S INPUT
  log "reglas IPv6 (INPUT):"
  "$IP6TABLES" -S INPUT
fi

log "hecho."
