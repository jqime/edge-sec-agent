# Resumen Ejecutivo — Edge Security Agent

**Versión:** 1.1.0 · **Fecha:** 2026-10-17 · **Hardware:** Orange Pi Zero 3 (ARM64) · **SO:** Debian 13 (trixie)

## 1. Qué es

Agente DevSecOps autónomo para entornos Edge Computing que endurece el perímetro de un nodo ARM64 sin dependencia de la nube: proxy inverso endurecido, autenticación, rate limiting, baneo automático de fuerza bruta, firewall persistente y monitorización de seguridad, todo orquestado con systemd.

## 2. Antes → Después (remediación por lotes)

| Área | Antes (auditoría) | Después (verificado) |
|---|---|---|
| Secretos en Git | Token Telegram + password expuestos | **0 rastros en el histórico** |
| Chat/LLM | Roto (`_SECURE_AGENT_SCRIPT` literal) | **Funcional en producción** |
| Firewall | No persistente, IPv6 sin reglas | **Persistente IPv4 + IPv6 (unit idempotente)** |
| Rutas systemd | `/root/...` incompatible con `ProtectHome` | **Derivadas de `__file__`** |
| Timers | No instalados | **health + backup activos** (update opt-in OFF) |
| Staging | Activo sin documentar | **Retirado** |
| Legacy | 21 `mcp_tools` + 7 scripts con `/root` | **Movidos a `legacy/` + 3 bugs corregidos** |
| CI | Solo x86_64 | **x86_64 + ARM64 nativo + integración real** |
| Docs | Desactualizadas | **TL;DR honesto, api_spec v1.1.0** |
| `.git` | 51M | **21M (−30M)** |
| Tests | 38 passed | **49 passed + integración en ARM64** |
| PR #4 | Abierto obsoleto | **Cerrado** |
| Rama `stable` | 32 commits atrás | **Fast-forward a `main`** |
| Tag release | `v1.0` | **`v1.1.0`** |

## 3. Áreas de trabajo (10 lotes + purga)

| # | Área | Resultado |
|---|---|---|
| 0 | Snapshot | Backup verificado (bundle + tar) |
| 1 | Secretos | Token + password rotados; literal eliminado de tests |
| 2 | Chat | `/v1/chat/completions` y `/ask` con el binario real |
| 3 | Firewall | IPv4 + IPv6 persistente e idempotente |
| 4 | Rutas | `SECRETS_PATH`/`REPORTS_DIR` systemd-safe |
| 5 | Release | `stable` fast-forward + `v1.1.0` + PR #4 cerrado |
| 6 | Timers | health/backup activos; staging retirado |
| 7 | Legacy | `legacy/` + 7 `mcp_tools` reescritos + 3 bugs corregidos |
| 8 | Docs | README/api_spec/AGENTS/CHANGELOG/presentation_guide |
| 9 | CI | Matriz `ubuntu-latest` + `ubuntu-24.04-arm` con integración |
| + | Purga histórica | 51M → 21M, 0 secretos (`filter-repo`) |

## 4. Estado final verificado

```
Tests          49 passed (+1 integración deselected)
Coverage       55% (src/sec_web.py 70%)
CI             x86_64 success · ARM64 success (+ integración real)
Servicios      edge-sec-agent · nginx · fail2ban · tailscaled · ollama → active
systemd        0 units failed
Salud API      HEALTHY (Ollama ok, SQLite ok)
Repo           21M · 111 commits · ramas remotas: main, stable · tags: v1.0, v1.1.0
Secretos       0 en histórico
```

## 5. Endpoints REST
`/` · `/v1/global/health` · `/metrics` · `/api/metrics` · `/v1/models` · `/v1/chat/completions` · `/ask` (Nginx `:8443`, TLS + Basic Auth).

## 6. Arquitectura de seguridad (defensa en profundidad)
- **Nginx `:8443`**: TLS 1.2/1.3, Basic Auth, rate limiting, security headers.
- **Gunicorn `:5000`**: solo loopback.
- **Ollama `:11434`**: solo loopback.
- **Firewall**: `DROP` en `:22`; `:5000`/`:11434` solo loopback; SSH `:2222` restringido a `tailscale0`.
- **Fail2Ban**: jails `sshd` y `nginx-http-auth`.
- **systemd**: `ProtectHome=true`, `ProtectSystem=strict`, usuario `edgesec`.

## 7. Limitaciones conocidas
- Purga del histórico de GitHub completa; objetos inalcanzables pueden persistir hasta GC interno.
- CI ARM64 nativo validado para tests; sin pruebas de hardware físico en CI.
- Bloat residual no-secreto: `picoclaw_aarch64.deb` (~20 MB) en histórico.

## 8. Documentación
`README.md` · `CHANGELOG.md` · `AGENTS.md` · `docs/OPERATIONS.md` · `docs/RECOVERY_RUNBOOK.md` · `docs/api_spec.yaml` · `docs/presentation_guide.md` · `docs/architecture.txt` · `docs/ROADMAP.md`.
