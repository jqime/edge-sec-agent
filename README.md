<div align="center">

# Edge Security Agent

**Autonomous perimeter security and DevSecOps observability for ARM64 edge devices**

[![CI](https://github.com/jqime/edge-sec-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/jqime/edge-sec-agent/actions/workflows/ci.yml)
![Release](https://img.shields.io/badge/release-v1.2.0-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-ARM64%20%7C%20Debian%2013-lightgrey)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

</div>

## What it is

**Edge Security Agent** is a self-hosted security appliance for low-resource
ARM64 nodes. It was built for an Orange Pi Zero 3 running Debian 13 and
combines perimeter hardening, local AI, intrusion detection, honeypot telemetry,
backup, health monitoring and safe updates on a single device.

It is designed to keep operational data and inference on the node: the
administration plane does not require a cloud service and Ollama runs a local
model for security reporting. External integrations are optional.

## Why it exists

A conventional microservice or cloud security platform is too expensive for a
small edge node. This project provides practical, auditable control over a
homelab or laboratory perimeter while remaining maintainable under constrained
CPU and RAM.

The implementation addresses four problems:

- **Perimeter exposure:** restrict management and administrative ports.
- **Incident visibility:** collect security scores, failed SSH attempts,
  Fail2Ban bans and honeypot events.
- **Operational resilience:** verify health, create backups and roll back unsafe
  updates.
- **Local decision support:** generate security reports through a local LLM
  without sending device data to the cloud.

## Implemented capabilities

### Perimeter hardening

- Nginx TLS 1.2/1.3 termination on port `8443`.
- HTTP Basic Authentication and a `5 requests/s` rate limit.
- Security headers including HSTS, `X-Frame-Options`, CSP-friendly framing
  controls, MIME sniffing protection and referrer policy.
- Persistent and idempotent IPv4/IPv6 firewall rules.
- Legacy SSH port `22` blocked.
- Dropbear administration restricted to the Tailscale interface on port `2222`.
- Gunicorn and Ollama bound to loopback only.
- Fail2Ban integration for SSH and Nginx authentication failures.
- Dedicated Cowrie SSH honeypot on port `2223`.

### Monitoring and observability

- Flask REST API behind Nginx.
- Prometheus-compatible `/metrics` endpoint.
- Live security metrics at `/api/metrics`.
- Structured health endpoint at `/v1/global/health`.
- SQLite/WAL persistence with 30-day metric retention.
- CPU temperature, RAM, uptime, SSH failures, open ports and Fail2Ban bans.
- Build and last-update metadata in metrics.
- Aggregated Cowrie telemetry without exposing passwords or commands.

### Local edge AI

- Ollama on loopback, with `tinyllama:1.1b` for the production security report.
- OpenAI-shaped `/v1/models` and `/v1/chat/completions` endpoints.
- Legacy `/ask` compatibility.
- Isolated Cowrie RAG CLI using `nomic-embed-text` and `sqlite-vec`.
- No PyTorch dependency in the RAG environment.

### Automation and recovery

- systemd watchdog every two minutes.
- Hourly backup timer with SQLite integrity checks.
- SHA-256 backup manifests and configurable retention.
- Restore workflow for SQLite and reports.
- Opt-in, locked safe-update timer.
- Pre-update validation and health-check based rollback.
- Explicit protection against updating `main` or `master` without consent.

## Infrastructure topology

```text
Internet / LAN
      |
      v
Nginx :8443
TLS + Basic Auth + rate limiting + security headers
      |
      v
Gunicorn :5000
loopback only
      |
      +--> Flask API
      |       |
      |       +--> SQLite /opt/edge-sec-agent/data/history.db
      |       +--> Local reports and backups
      |
      +--> Ollama :11434
              loopback only

Tailscale tailnet
      |
      +--> Dropbear :2222
      +--> Cowrie honeypot :2223
      +--> Administration endpoints
```

### Network exposure

| Port | Service | Exposure | Controls |
|---:|---|---|---|
| `22` | Legacy SSH | None | IPv4/IPv6 `DROP` |
| `2222` | Dropbear | Tailscale interface | Tailnet-only access |
| `8443` | Nginx | Configured network interfaces | TLS, authentication, rate limit, headers |
| `5000` | Gunicorn | `127.0.0.1` | Loopback only |
| `11434` | Ollama | `127.0.0.1` | Loopback only |
| `2223` | Cowrie | Tailscale interface | Isolated user, directory and network filtering |
| `41641/UDP` | Tailscale | Tailnet transport | WireGuard tunnel |

The complete documented topology is in
[`docs/architecture.txt`](docs/architecture.txt).

## Honesty about deployment status

The following points are based on the device and repository evidence collected
for this project:

| Area | Verified state |
|---|---|
| Repository secrets | Legacy Telegram token and Basic Auth password rotated |
| Chat report endpoint | Repaired and tested |
| Firewall | Persistent IPv4/IPv6 rules, without flushing Tailscale chains |
| CI | x86_64 and native ARM64 matrix |
| Production host | Orange Pi Zero 3 / Debian 13 validated manually |
| Honeypot | Cowrie isolated, Tailscale-only, tested with controlled access |
| Honeypot telemetry | Cowrie JSON log captured and summarized |
| RAG | CLI Phase 2 completed and validated |
| Automatic updates | Implemented but disabled by default |

The public Internet honeypot sensor is not enabled by default. Captured
Tailscale and local events prove the sensor works, but they are not evidence of
public Internet attacks. Real public capture would require an explicit router
port-forwarding decision.

## Quick start

### Requirements

- Orange Pi Zero 3 or compatible ARM64 Debian 13 system.
- Minimum 450 MB available memory and 2 GB free disk space for the bootstrap.
- Root access for initial service installation.
- Debian/DietPi compatibility.
- Optional Tailscale for remote administration.
- Optional Ollama for local AI reports.

### One-command bootstrap

```bash
curl -fsSL https://raw.githubusercontent.com/jqime/edge-sec-agent/main/install.sh \
  | sudo bash -s stable
```

The bootstrap clones the selected channel, creates the `edgesec` service user,
prepares persistent directories, creates the application virtual environment,
installs systemd units and activates the core services.

### Manual bootstrap

```bash
git clone https://github.com/jqime/edge-sec-agent.git
cd edge-sec-agent
sudo ./scripts/bootstrap_debian_arm64.sh --channel stable
```

Use `--dry-run` to validate architecture, OS, memory and repository availability
before applying changes:

```bash
sudo ./scripts/bootstrap_debian_arm64.sh --channel stable --dry-run
```

### Verify the installation

```bash
curl -s http://127.0.0.1:5000/v1/global/health
curl -s http://127.0.0.1:5000/api/metrics
curl -s http://127.0.0.1:5000/metrics

systemctl status edge-sec-agent edge-firewall
systemctl list-timers --all | grep edge
journalctl -u edge-sec-agent -f
```

The public API is also served through Nginx on port `8443` and requires Basic
Authentication.

## API surface

| Endpoint | Method | Purpose |
|---|---|---|
| `/v1/global/health` | `GET` | Dependencies, temperature, RAM, uptime and health state |
| `/api/metrics` | `GET` | Live security score and infrastructure metrics |
| `/metrics` | `GET` | Prometheus text exposition |
| `/v1/models` | `GET` | OpenAI-shaped model discovery |
| `/v1/chat/completions` | `POST` | Security report compatible with OpenAI clients |
| `/ask` | `POST` | Legacy security report endpoint |
| `/api/honeypot/summary` | `GET` | Aggregate Cowrie counts and source IPs |

The honeypot summary intentionally excludes usernames, passwords and command
payloads. The OpenAPI contract is maintained in
[`docs/api_spec.yaml`](docs/api_spec.yaml).

## Operations

Canonical installation layout:

```text
/opt/edge-sec-agent/
├── app/current/       Versioned repository and scripts
├── app/venv/          Application Python environment
├── config/            Non-secret runtime environment
├── data/              SQLite database and update metadata
├── reports/           Generated security reports
├── backups/           Verified backups
├── logs/              Service-owned runtime logs
└── secrets.env        Local secrets, excluded from Git
```

Use the operations and recovery runbooks for deployment, restore and incident
procedures:

- [`docs/OPERATIONS.md`](docs/OPERATIONS.md)
- [`docs/RECOVERY_RUNBOOK.md`](docs/RECOVERY_RUNBOOK.md)
- [`docs/HONEYPOT.md`](docs/HONEYPOT.md)
- [`docs/RAG.md`](docs/RAG.md)

### Backup

```bash
sudo /opt/edge-sec-agent/app/current/scripts/backup_state.sh
```

### Restore

```bash
sudo /opt/edge-sec-agent/app/current/scripts/restore_state.sh \
  /opt/edge-sec-agent/backups/<timestamp>
```

Backups include SQLite data, reports, a manifest and SHA-256 checksums. SQLite
copies are checked with `PRAGMA integrity_check` before they are considered
valid.

### Opt-in safe updates

```bash
sudo mkdir -p /etc/edge-sec-agent
sudo touch /etc/edge-sec-agent/update.enabled
sudo systemctl enable --now edge-sec-agent-update.timer
```

The updater rejects dirty local repositories, locks concurrent executions,
backs up before changing the checkout, runs validation, restarts only the agent,
checks health and restores the previous commit when the service fails.

## Development and testing

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

.venv/bin/pytest tests/ -q
.venv/bin/pytest tests/ -m integration -q
.venv/bin/ruff check src/ tests/
.venv/bin/mypy src/ --ignore-missing-imports
python3 -m compileall src/
bash -n scripts/*.sh install.sh
```

To install commit checks locally:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

The CI pipeline validates Python, shell syntax and systemd units on both
`ubuntu-latest` and a native ARM64 runner. An integration test executes the real
agent binary with isolated database and report paths.

## Security model and limitations

- Secrets must remain outside Git, with restrictive ownership and permissions.
- Nginx authentication protects the HTTP administration plane.
- Gunicorn and Ollama are only reachable through loopback.
- Tailscale restricts administrative and honeypot ingress.
- systemd uses a non-login service user, `ProtectHome=true`,
  `ProtectSystem=strict` and restricted writable paths where applicable.
- A firewall unit does not flush unrelated Tailscale or Docker chains.
- CI validates architecture compatibility but cannot replace host-specific
  thermal, network and hardware testing.
- The RAG CLI is intentionally isolated from the production virtual environment.
- Current RAG responses are suitable for delayed, factual log consultation, not
  real-time incident analysis.
- The repository history has been purged of legacy secrets, but GitHub objects
  retained by the platform or external clones are outside repository control.
- One non-secret bloat artifact remains in Git history pending an explicit,
  owner-approved `filter-repo` operation.

## Roadmap

The prioritized backlog is documented in [`docs/ROADMAP.md`](docs/ROADMAP.md).
The next safe improvements are:

1. Merge and validate the reproducible bootstrap change in CI.
2. Add pre-commit secret and static-analysis enforcement.
3. Add contract tests for `docs/api_spec.yaml`.
4. Expand integration coverage beyond the chat report path.
5. Add Telegram threshold alerts for temperature, RAM and security score.
6. Add an optional Grafana/Prometheus node for dashboards.
7. Integrate the isolated Cowrie RAG as an opt-in API feature only after
   capacity and performance validation.

## Project documentation

| Document | Description |
|---|---|
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | Deployment, services and firewall operation |
| [`docs/RECOVERY_RUNBOOK.md`](docs/RECOVERY_RUNBOOK.md) | Backup and recovery procedures |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Design decisions and request flow |
| [`docs/HONEYPOT.md`](docs/HONEYPOT.md) | Cowrie installation, evidence and limitations |
| [`docs/RAG.md`](docs/RAG.md) | Isolated Cowrie RAG architecture and usage |
| [`docs/api_spec.yaml`](docs/api_spec.yaml) | OpenAPI 3.0.3 REST contract |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Prioritized improvements |

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE).
