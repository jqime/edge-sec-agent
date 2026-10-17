<div align="center">

# Edge Security Agent

Autonomous DevSecOps and Perimeter Defense for ARM64 Edge Devices

[![CI](https://github.com/jqime/edge-sec-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/jqime/edge-sec-agent/actions/workflows/ci.yml)
![Release](https://img.shields.io/badge/release-v1.1.0-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-ARM64%20%7C%20Debian%2013-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)
![Repo Size](https://img.shields.io/badge/repo_size-1.3_MB-brightgreen)

</div>

## Overview

Edge Security Agent is a self-contained security appliance for low-resource ARM64 hardware (Orange Pi Zero 3, Debian 13 "trixie"). It provides a hardened reverse proxy, local AI inference through Ollama, Fail2Ban intrusion prevention, and a REST/Prometheus observability surface, with no cloud dependency.

### The Journey

The project was audited and remediated across ten tracked workstreams. The remediation path is documented to demonstrate engineering maturity rather than a "clean-room" history.

| Area | Before (Audit) | Current State (Verified) |
|---|---|---|
| Secrets in Git History | Exposed | 0 traces (Rotated & Purged) |
| Chat / LLM Endpoint | Broken | Functional (Security Reports) |
| Firewall | Not persistent, no IPv6 | Persistent IPv4 + IPv6 |
| CI Pipeline | x86_64 only | x86_64 + Native ARM64 |
| Repository Size | 51 MB | 1.3 MB (purged history) |

## Architecture & Topology

```
Internet
    |
    v
Nginx :8443  (TLS 1.2/1.3, Basic Auth, rate limiting, hardening headers)
    |  proxy_pass -> 127.0.0.1:5000
    v
Gunicorn :5000  (loopback only)
    |
    v
Flask API  (src/sec_web.py)
    |
    +--> Ollama :11434  (loopback, local LLM)
    |
    +--> SQLite  (data/history.db, WAL)

Tailscale (tailnet)
    |
    v
Dropbear :2222  (tailscale0 interface only)
```

### Port Matrix

| Port | Service | Interface | Security Control |
|---|---|---|---|
| 22 | Legacy SSH | none | `iptables DROP` (IPv4 + IPv6) |
| 2222 | Dropbear SSH | `tailscale0` only | tailnet-restricted access |
| 8443 | Nginx (HTTPS) | public | TLS 1.2/1.3, Basic Auth, 5 r/s rate limit, security headers |
| 5000 | Gunicorn / Flask API | `127.0.0.1` | loopback only, `DROP` externally |
| 11434 | Ollama (local LLM) | `127.0.0.1` | loopback only, `DROP` externally |
| 2223 | Cowrie Honeypot | `tailscale0` only | isolated sensor, `DROP` elsewhere |
| 41641 | Tailscale (WireGuard) | UDP | tailnet VPN |

The complete topology diagram is available at [docs/architecture.txt](docs/architecture.txt).

## Core Capabilities

### Perimeter Hardening

- **Nginx**: TLS 1.2/1.3 termination, HTTP Basic Auth, rate limiting (5 requests/second, burst 10) and hardening headers (HSTS, `X-Frame-Options DENY`, `X-Content-Type-Options nosniff`, `Referrer-Policy`).
- **Fail2Ban**: custom jails for `sshd` and `nginx-http-auth`.
- **Firewall**: idempotent persistence via `edge-firewall.service`, applied over both IPv4 and IPv6.
- **SSH**: port 22 is dropped at the kernel level; administration is restricted to Dropbear on the `tailscale0` interface.
- **Honeypot**: an isolated Cowrie SSH sensor on `:2223` (dedicated user and directory) records attacker credentials and commands and dispatches alerts to Telegram. See [docs/HONEYPOT.md](docs/HONEYPOT.md).

### Edge AI and Observability

- **Local LLM**: Ollama integration (`tinyllama:1.1b`) for automated security reporting and latency/health probing.
- **REST API**: OpenAI-shaped endpoints (`/v1/models`, `/v1/chat/completions`) returning live security reports and metrics. The completions endpoint returns a security report and is not a free-form chat interface.
- **Telemetry**: Prometheus `/metrics` endpoint, a live security score at `/api/metrics`, and SQLite (WAL) historical retention with a 30-day policy.
- **Honeypot RAG (Phase 2)**: natural-language queries over Cowrie logs via Ollama embeddings (`nomic-embed-text`) + `sqlite-vec`, executed from an isolated venv (`scripts/rag_query.py`). No PyTorch, no production impact. See `docs/RAG.md`.

### DevSecOps Automation

- **Systemd Timers**: `edge-sec-agent-health.timer` (watchdog) and `edge-sec-agent-backup.timer` (backups verified with SQLite `integrity_check` and a SHA256 manifest).
- **Safe Updates**: opt-in update mechanism (`edge-sec-agent-update.timer`, disabled by default) with lock handling, health check and automatic rollback.
- **CI Matrix**: cross-architecture validation (x86_64 + native ARM64) executing real integration tests on the production architecture.

## Quickstart

Requirements: ARM64 hardware, Debian 13 (trixie) or DietPi, and root access for provisioning.

```bash
git clone https://github.com/jqime/edge-sec-agent.git
cd edge-sec-agent
sudo ./scripts/bootstrap_debian_arm64.sh --channel stable
```

Verification:

```bash
curl -s http://127.0.0.1:5000/v1/global/health
journalctl -u edge-sec-agent -f
```

## Documentation & Governance

| Document | Description |
|---|---|
| [Operations Runbook](docs/OPERATIONS.md) | Deployment, systemd, and firewall management. |
| [Recovery Runbook](docs/RECOVERY_RUNBOOK.md) | Disaster recovery procedures. |
| [API Specification](docs/api_spec.yaml) | OpenAPI 3.0.3 contract. |
| [Architecture](docs/architecture.txt) | Network and infrastructure topology. |

## Testing & CI

The suite contains 49 unit tests and 1 integration test, with a measured coverage of 55%. The integration test executes the real agent binary against an isolated temporary database and report directory.

The CI pipeline runs on a matrix of `ubuntu-latest` (x86_64) and `ubuntu-24.04-arm` (native ARM64). Each job executes `ruff`, `mypy`, `pytest`, `compileall`, Bash syntax validation, and `systemd-analyze verify`; the integration test runs only on the ARM64 runner.

```bash
pytest tests/ -q                 # unit suite
pytest tests/ -m integration -q  # integration test
```

## Security & Limitations

- The repository history has been purged of legacy secrets. Active secrets must be managed outside version control at `/opt/edge-sec-agent/secrets.env` (mode `600`, owner `edgesec:edgesec`).
- CI validates x86_64 and ARM64 runners; the physical hardware target is an Orange Pi Zero 3, validated manually.
- A non-secret bloat artifact (`picoclaw_aarch64.deb`, approximately 20 MB) remains in the Git history pending a future purge.
- The Python packaging version in `pyproject.toml` is `1.0.0`, whereas the release tag is `v1.1.0`.

A prioritized list of pending improvements is maintained in [docs/ROADMAP.md](docs/ROADMAP.md).

## License

Distributed under the MIT License. See [LICENSE](LICENSE).

Copyright (c) 2026 Edge Security Agent Contributors.
