<div align="center">

# Edge Security Agent

**Autonomous DevSecOps & Perimeter Defense for ARM64 Edge Devices**

[![CI](https://github.com/jqime/edge-sec-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/jqime/edge-sec-agent/actions/workflows/ci.yml)
![Release](https://img.shields.io/badge/release-v1.1.0-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-ARM64%20%7C%20Debian%2013-orange)
![License](https://img.shields.io/badge/license-MIT-green)

An autonomous security and observability agent for low-resource hardware. Hardened reverse proxy, local AI (Ollama), Fail2Ban and a REST dashboard — with no cloud dependency.

</div>

---

## 📖 Overview

Edge Security Agent turns a single ARM64 board (Orange Pi Zero 3, Debian 13 “trixie”) into a self-contained security appliance: TLS-terminated reverse proxy, authentication, rate limiting, brute-force banning, a persistent firewall, local LLM probes and a Prometheus/REST observability surface — all orchestrated by `systemd`.

### The Journey

Built, audited, and remediated across 10 tracked workstreams. The project deliberately documents its own hardening path:

| Area | Before (audit) | Now (verified) |
|---|---|---|
| Secrets in Git history | Token + password exposed | **0 traces** (rotated + history purged) |
| Chat / LLM endpoint | Broken | **Functional in production** |
| Firewall | Not persistent, no IPv6 rules | **Persistent IPv4 + IPv6** (idempotent unit) |
| systemd-safe paths | `/root/...` (incompatible with `ProtectHome`) | **Derived from `__file__`** |
| CI | x86_64 only | **x86_64 + native ARM64** (+ integration) |
| Repository size | 51 MB | **21 MB** |

---

## 🏗️ Architecture & Network Topology

```
Internet ──▶ Nginx :8443 (TLS 1.2/1.3 · Basic Auth · rate limit · headers)
                 └─▶ Gunicorn :5000 (loopback only) ─▶ Flask core ─▶ SQLite (WAL)
Tailscale ─▶ Dropbear :2222 (tailscale0 only)
```

### Port matrix

| Port | Service | Interface | Security control |
|---|---|---|---|
| 22 | (legacy SSH) | — | `iptables DROP` (IPv4 + IPv6) |
| 2222 | Dropbear SSH | `tailscale0` only | Tailscale-only access |
| 8443 | Nginx (HTTPS) | public | TLS 1.2/1.3, Basic Auth, 5 r/s rate limit, security headers |
| 5000 | Gunicorn / Flask API | `127.0.0.1` | loopback-only, `DROP` externally |
| 11434 | Ollama (local LLM) | `127.0.0.1` | loopback-only, `DROP` externally |
| 41641 | Tailscale (WireGuard) | UDP | tailnet VPN |

Full diagram: [`docs/architecture.txt`](docs/architecture.txt).

---

## ✨ Key Features

### 🛡️ Perimeter Hardening
- **Nginx** reverse proxy with TLS 1.2/1.3, HTTP Basic Auth, rate limiting and hardening headers (HSTS, `X-Frame-Options DENY`, `nosniff`, `Referrer-Policy`).
- **Fail2Ban** with dedicated jails for `sshd` and `nginx-http-auth`.
- **Persistent, idempotent firewall** (IPv4 + IPv6) via `edge-firewall.service`; internal ports (`5000`, `11434`) reachable only over loopback.
- **SSH exposure removed**: port 22 dropped at the kernel; administration moved to Dropbear `:2222`, restricted to the `tailscale0` interface.

### 🧠 Edge AI & Observability
- **OpenAI-shaped endpoints**: `/v1/models` and `/v1/chat/completions` (the completions endpoint runs the security agent and returns its report; it is not a free-form chat).
- **Local LLM** via Ollama (`tinyllama:1.1b`) with latency/health probes.
- **SQLite (WAL)** history with automatic 30-day retention.
- **Prometheus `/metrics`** plus a live security score at `/api/metrics`.

### ⚙️ DevSecOps Automation
- **systemd timers**: `edge-sec-agent-health.timer` (watchdog) and `edge-sec-agent-backup.timer` (backup with SQLite `integrity_check` + `sha256sum` manifest).
- **Safe, opt-in updates** (`edge-sec-agent-update.timer`, disabled by default) with lock, health check and rollback.
- **CI matrix**: x86_64 and **native ARM64** (`ubuntu-24.04-arm`), including real integration tests.

---

## 🚀 Quickstart

**Requirements:** ARM64 board running Debian 13 / DietPi; root for bootstrap; Tailscale recommended for administration.

```bash
# 1. Clone
git clone https://github.com/jqime/edge-sec-agent.git
cd edge-sec-agent

# 2. Bootstrap (idempotent: venv, systemd units, permissions)
sudo ./scripts/bootstrap_debian_arm64.sh --channel stable

# 3. Configure secrets OUTSIDE the repo
#    /opt/edge-sec-agent/config/edge-sec-agent.env  (and secrets.env, mode 600)

# 4. Verify health (loopback)
curl -s http://127.0.0.1:5000/v1/global/health | jq .

# 5. Follow logs
journalctl -u edge-sec-agent -f
```

Operational and recovery guides: [`docs/OPERATIONS.md`](docs/OPERATIONS.md) · [`docs/RECOVERY_RUNBOOK.md`](docs/RECOVERY_RUNBOOK.md).

---

## 📁 Project Structure

```
edge-sec-agent/
├── src/              # Core: agent.py (engine), sec_web.py (Flask API), database.py (SQLite)
├── scripts/          # Bootstrap, firewall, backup/restore, safe update, CLI (sec, sec-agent, sec-chat)
├── systemd/          # Units & timers (agent, firewall, health, backup, update)
├── mcp_tools/        # Supported diagnostic tools
├── legacy/           # Obsolete tools — NOT supported, do not use in production
├── docs/             # Operations, recovery, api_spec, architecture, executive summary, roadmap
├── tests/            # pytest suite (+ integration test)
├── data/             # Runtime data (SQLite history.db) — not versioned
├── wsgi.py           # Gunicorn entry point
└── nginx_agent.conf  # Reference reverse-proxy configuration
```

> The directory `legacy/` contains tools moved out by technical debt. It is versioned for reference only and carries **no support**.

---

## 📚 Documentation & Delivery

| Document | Purpose |
|---|---|
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | Operation runbook (paths, systemd, firewall, CI) |
| [`docs/RECOVERY_RUNBOOK.md`](docs/RECOVERY_RUNBOOK.md) | Disaster recovery |
| [`docs/RESUMEN_EJECUTIVO.md`](docs/RESUMEN_EJECUTIVO.md) | Executive summary |
| [`docs/presentation_guide.md`](docs/presentation_guide.md) | Deep dive / tribunal Q&A |
| [`docs/architecture.txt`](docs/architecture.txt) | Network & architecture diagram |
| [`docs/api_spec.yaml`](docs/api_spec.yaml) | OpenAPI 3.0.3 contract |

---

## 🧪 Testing & CI

- **49 unit tests** + **1 integration test** (`test_chat_integration_runs_real_agent`), coverage **55%**.
- The integration test runs the real binary against isolated `tmp` DB/reports; it executes in CI **only on ARM64** (the production architecture).
- CI validates, on both x86_64 and ARM64: `ruff`, `mypy`, `pytest`, `compileall`, Bash syntax and `systemd-analyze verify`.

```bash
pytest tests/ -q                 # unit suite
pytest tests/ -m integration -q  # integration (runs the real agent)
```

---

## 🛣️ Roadmap & Limitations

See [`docs/ROADMAP.md`](docs/ROADMAP.md). Honest constraints:

- CI validates **x86_64 and ARM64 runners**; the real hardware target is an Orange Pi Zero 3 (validated manually).
- A non-secret historical bloat artifact remains (`picoclaw_aarch64.deb`, ~20 MB) pending a future history purge.
- `pyproject.toml` still reports package version `1.0.0` while the release tag is `v1.1.0`.

---

## ⚖️ License

Released under the **MIT License**. See [`LICENSE`](LICENSE). Copyright (c) 2026 Edge Security Agent Contributors.
