#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${EDGE_REPO_URL:-https://github.com/jqime/edge-sec-agent.git}"
CHANNEL="${1:-stable}"
INSTALL_ROOT="${EDGE_INSTALL_ROOT:-/opt/edge-sec-agent}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Este instalador necesita root: sudo $0 [stable|tag]" >&2
  exit 1
fi

command -v git >/dev/null 2>&1 || {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq git ca-certificates
}

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

echo "Descargando Edge Sec Agent (${CHANNEL})..."
git clone --depth 1 --branch "$CHANNEL" "$REPO_URL" "$tmp_dir/edge-sec-agent"

exec "$tmp_dir/edge-sec-agent/scripts/bootstrap_debian_arm64.sh" \
  --repo-url "$REPO_URL" \
  --channel "$CHANNEL" \
  --install-root "$INSTALL_ROOT"
