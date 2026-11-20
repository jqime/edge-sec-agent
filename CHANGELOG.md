# Changelog

All notable changes to this project will be documented in this file.

## [1.2.0] - 2026-11-20

### Added
- Single-command ARM64 bootstrap entry point (`install.sh`) for the stable channel.
- Honeypot summary endpoint (`/api/honeypot/summary`) with aggregated event counts and source IPs.
- Live security score calculation for health and Prometheus endpoints.
- Deployment metadata persisted in `data/last_update.json`.
- Compatibility paths for legacy installations under `/opt/edge-sec-agent`.
- Professional project README describing architecture, deployment, operations and limitations.

### Changed
- Production systemd units use `/opt/edge-sec-agent/app/current` and `/opt/edge-sec-agent/app/venv`.
- Backup, health, firewall and Cowrie units use canonical deployment paths.
- Safe updater uses the installed application virtual environment.
- Git operations accept the service-owned checkout without global `safe.directory` changes.
- CI uses `actions/checkout@v4`, `actions/setup-python@v5` and explicit read-only permissions.

### Fixed
- Systemd validation now substitutes Cowrie and firewall executable paths.
- OpenAPI model and honeypot schemas are structurally consistent.
- Legacy production layouts are preserved during bootstrap instead of being replaced.
- Prometheus no longer reports stale or null security score values when SQLite has no recent metric.

### Validated
- CI passed on `ubuntu-latest` and `ubuntu-24.04-arm`.
- Orange Pi Zero 3 deployment reports `HEALTHY`.
- Ollama, SQLite, Cowrie, Nginx, Fail2Ban, Tailscale and the edge timers are active.

## [1.1.0] - 2026-10-17

### Security
- Rotados token de Telegram y password de Basic Auth (expuestos en el histórico).
- Eliminado el literal `REDACTED` de `tests/live_demo_trigger.ps1`.
- Firewall persistente IPv4 + IPv6 (unit `edge-firewall` idempotente).
- `SECRETS_PATH` y `REPORTS_DIR` derivados de `__file__` (systemd-safe).

### Fixed
- `/v1/chat/completions` y `/ask`: usan la variable real `_SECURE_AGENT_SCRIPT` en lugar del literal. Test cómplice reescrito.
- `source secrets.env` ya no aborta bajo `set -euo pipefail` (hash `$apr1$`).
- `sec-chat`: path corregido a `mcp_tools/` real.
- `check_cpu`: lógica de alerta corregida.

### Changed
- `stable` fast-forward a `main`. Tag `v1.1.0`.
- Timers `edge-sec-agent-health` y `edge-sec-agent-backup` activos; `update.timer` OFF (opt-in).
- Staging retirado.
- Legacy (14 ficheros) movido a `legacy/`.
- README con sección "Estado actual (TL;DR honesto)".

### Removed
- `app/` (shim PR#4 roto).
- Worktree `/root/edge-sec-agent-pr4`.
- Cruft `.bak` en `/etc/systemd/system/`.

## [1.0.0] - 2026-05-17

### Added
- Core security agent with Flask REST API (`src/agent.py`, `src/sec_web.py`)
- SQLite persistence with automatic 30-day data retention (`src/database.py`)
- Nginx reverse proxy with TLS 1.2/1.3, Basic Auth, Rate Limiting, and Security Headers (`nginx_agent.conf`)
- Gunicorn WSGI production server with systemd persistence (`edge-sec-agent.service`, `wsgi.py`)
- Fail2Ban integration with `dropbear` and `nginx-http-auth` jails
- MCP diagnostic tools: `check_disk`, `check_cpu`, `check_ram`, `check_fail2ban`, `check_connections`, `check_updates`, `check_processes`, `show_history`, `log-analyzer`
- Automated 7-step deployment script (`scripts/remote_deploy.sh`)
- Perimeter security audit script with 5 verification checks (`scripts/security_audit.sh`)
- PowerShell 5.1 live demo trigger for brute force simulation (`tests/live_demo_trigger.ps1`)
- Tribunal presentation guide (`docs/presentation_guide.md`)
- SSH hardening: port migration to 2222, iptables DROP on port 22 (IPv4 + IPv6)
- Prometheus-compatible `/metrics` endpoint
- Structured `/v1/global/health` health check endpoint

### Security
- Firewall: iptables DROP rule on port 22 (persistent)
- TLS: Self-signed 2048-bit certificate, 365-day validity
- Rate Limiting: 5 req/s per IP with burst of 10
- Basic Auth: HTTP authentication on all Nginx endpoints
- Security Headers: HSTS, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy
- Backend isolation: Gunicorn bound to 127.0.0.1:5000 only

### Optimizations
- DietPi-Ramlog integration for in-memory log processing
- SQLite write amplification mitigation via `prune_old_metrics()`
- Fail2Ban `backend = auto` for RAM-based log monitoring
