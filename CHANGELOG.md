# Changelog

All notable changes to this project will be documented in this file.

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
