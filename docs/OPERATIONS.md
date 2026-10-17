# Operación de Edge Sec Agent (ARM64)

## Objetivo

Este documento define una ruta reproducible para desplegar y operar `edge-sec-agent` en Orange Pi / Debian ARM64 separando:

- **Código versionado:** `/opt/edge-sec-agent/app/current`
- **Configuración y secrets fuera de Git:** `/opt/edge-sec-agent/config`
- **Datos persistentes:** `/opt/edge-sec-agent/data`
- **Reportes y backups:** `/opt/edge-sec-agent/reports`, `/opt/edge-sec-agent/backups`

## Jerarquía de rutas

| Recurso | Ruta | Notas |
|---|---|---|
| Código | `/opt/edge-sec-agent` (actual) / `/opt/edge-sec-agent/app/current` (layout futuro) | Fuente de verdad del despliegue actual |
| Configuración | `/opt/edge-sec-agent/config/` | `edge-sec-agent.env`, `640 root:edgesec`, sin secretos |
| Secretos | `/opt/edge-sec-agent/secrets.env` | `600 edgesec:edgesec`, fuera de Git |
| Datos | `/opt/edge-sec-agent/data/` | SQLite (`history.db`), `ReadWritePaths` del unit |
| Reportes | `/opt/edge-sec-agent/reports/` | `ReadWritePaths` del unit |
| Backups | `/opt/edge-sec-agent/backups/` | `ReadWritePaths` del unit |
| Logs | `/opt/edge-sec-agent/logs/` | `ReadWritePaths` del unit |

El unit de producción corre con `User=edgesec`, `ProtectHome=true` y
`ProtectSystem=strict`. Por eso **ninguna ruta viva puede depender de `/root`**:
`/root` queda oculto para el proceso y cualquier `os.path.exists()` sobre él
devuelve `False` en silencio.

Las rutas del código se derivan de `__file__` (nunca hardcodeadas) y admiten
sobreescritura por variable de entorno:

- Reportes: `REPORTS_DIR` → `EDGE_REPORTS_DIR` → `<raíz del proyecto>/reports`
- Secretos: `SECRETS_PATH` → `EDGE_SECRETS_PATH` → `<raíz del proyecto>/secrets.env`

## Bootstrap idempotente desde cero

> Requiere root y Debian/DietPi ARM64.

```bash
sudo /opt/edge-sec-agent/app/current/scripts/bootstrap_debian_arm64.sh \
  --repo-url https://github.com/jqime/edge-sec-agent.git \
  --channel stable
```

El bootstrap valida arquitectura/memoria/espacio, crea `edgesec`, instala dependencias mínimas, prepara rutas persistentes, instala units de systemd y **no borra** datos existentes.

## Servicios systemd

Units del repositorio (`systemd/`) y estado esperado en el host:

| Unit | Instalado | Estado |
|---|---|---|
| `edge-sec-agent.service` | Sí | enabled/active (API Gunicorn, `User=edgesec`) |
| `edge-firewall.service` | Sí | enabled/active (oneshot, firewall idempotente) |
| `edge-sec-agent-health.timer` + `.service` | Sí | enabled/active (watchdog cada 2 min) |
| `edge-sec-agent-backup.timer` + `.service` | Sí | enabled/active (backup horario) |
| `edge-sec-agent-update.timer` + `.service` | **No** | **opt-in OFF** (ver sección) |

Los `ExecStart` de los servicios `oneshot` apuntan al layout actual
(`/opt/edge-sec-agent/scripts/...`); el unit principal usa
`WorkingDirectory=/opt/edge-sec-agent` y `venv/bin/gunicorn`. **No** se usa el
layout obsoleto `app/current` + `app/venv` (symlinks rotos a `/root`, ilegibles
bajo `ProtectHome=true`).

> El unit `edge-sec-agent-staging.service` (`:5001`) fue **retirado**: era un
> checkout duplicado no versionado. Backup en
> `/var/backups/edge-sec-agent/staging-<timestamp>`.

Verificar timers:

```bash
systemctl list-timers --all | grep edge
systemctl status edge-sec-agent-health.timer edge-sec-agent-backup.timer --no-pager
journalctl -u edge-sec-agent-health.service -n 5 --no-pager
```

Ejecutar manualmente / deshabilitar:

```bash
sudo systemctl start edge-sec-agent-backup.service     # backup puntual
sudo systemctl disable --now edge-sec-agent-health.timer edge-sec-agent-backup.timer
```

Validación recomendada:

```bash
sudo systemd-analyze verify /etc/systemd/system/edge-sec-agent.service
```

## Actualización automática segura (opt-in)

La actualización está deshabilitada por defecto. Para habilitar:

```bash
sudo mkdir -p /etc/edge-sec-agent
sudo touch /etc/edge-sec-agent/update.enabled
sudo systemctl enable --now edge-sec-agent-update.timer
```

El flujo de `scripts/update_safe.sh` incluye:

1. lock (`flock`) para evitar concurrencia
2. rechazo si el repo tiene cambios locales
3. fetch/reset a un canal configurable (`EDGE_UPDATE_CHANNEL`, por defecto `stable`)
4. backup previo
5. validaciones (`compileall`, Ruff, Mypy, pytest)
6. restart de solo `edge-sec-agent`
7. health check post-update con rollback automático si falla

Protección adicional: `main/master` se bloquean salvo `EDGE_ALLOW_MAIN_UPDATE=1` explícito.

## Backups y restore

Backup:

```bash
sudo /opt/edge-sec-agent/app/current/scripts/backup_state.sh
```

Restore:

```bash
sudo /opt/edge-sec-agent/app/current/scripts/restore_state.sh \
  /opt/edge-sec-agent/backups/<timestamp>
```

Incluye SQLite + reportes, checksum SHA256 y verificación `PRAGMA integrity_check`.

## Watchdog y observabilidad

- `scripts/health_watchdog.sh` comprueba health endpoint, SQLite y puertos esperados.
- Si falla, reinicia únicamente `edge-sec-agent` y registra causa.
- `/metrics` exporta uptime, requests, errores HTTP, estado de Ollama, última actualización y commit.

## Firewall (IPv4 + IPv6)

El hardening de firewall lo gestiona `systemd/edge-firewall.service`, un unit
`oneshot` ordenado tras `tailscaled.service`. Aplica reglas **idempotentes**
(`iptables -C || -A`) mediante `scripts/apply_firewall.sh` y **nunca hace flush**
de la tabla `filter`, por lo que no interfiere con las cadenas de Tailscale
(`ts-input`/`ts-forward`).

Reglas (IPv4 e IPv6 en espejo):

- `ACCEPT` tcp 5000 y 11434 desde loopback (`127.0.0.1` / `::1`)
- `DROP` tcp 5000 y 11434 para el resto
- `ACCEPT` tcp 2222 entrando por `tailscale0` (SSH Dropbear)
- `DROP` tcp 2222 para el resto
- `DROP` tcp 22

Aplicar / simular / revertir:

```bash
sudo /opt/edge-sec-agent/scripts/apply_firewall.sh           # aplica (idempotente)
sudo /opt/edge-sec-agent/scripts/apply_firewall.sh --dry-run # simula sin cambiar
sudo /opt/edge-sec-agent/scripts/apply_firewall.sh --remove  # rollback
```

Instalar y activar la persistencia:

```bash
sudo cp /opt/edge-sec-agent/systemd/edge-firewall.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now edge-firewall.service
systemctl status edge-firewall --no-pager
sudo iptables -S INPUT
sudo ip6tables -S INPUT
```

Verificar tras reaplicar (sin reboot de la Pi):

```bash
sudo systemctl restart edge-firewall.service
sudo iptables -L INPUT -n -v --line-numbers   # la primera regla debe seguir siendo ts-input
sudo ip6tables -L INPUT -n -v --line-numbers
```

> **Advertencia Tailscale:** NO persistir las cadenas `ts-input`/`ts-forward`
> con `netfilter-persistent`/`iptables-restore`: `iptables-restore` hace flush
> de la tabla `filter` y puede romper el firewall de Tailscale (riesgo de
> lockout). Este unit evita ese escenario al no hacer flush y solo usar `-A`.

## Seguridad y privilegios

Tareas que requieren root:

- bootstrap inicial
- instalación/activación de units
- timers de backup/update/watchdog

Tareas sin root (`edgesec`):

- ejecución de Gunicorn/API
- lectura/escritura de datos y reportes en rutas permitidas

No se incluyen secretos en Git. Use `/opt/edge-sec-agent/config/edge-sec-agent.env` y almacénelos fuera del repositorio.

## CI cross-arch (x86_64 + ARM64)

El workflow `ci.yml` ejecuta la matriz `os: [ubuntu-latest, ubuntu-24.04-arm]`:

- `ubuntu-latest` (x86_64): validaciones estándar (ruff, mypy, pytest, compileall, `bash -n`, `systemd-analyze verify`).
- `ubuntu-24.04-arm` (ARM64 nativo): las mismas validaciones **más** los tests de integración reales.

El test `@pytest.mark.integration` (`test_chat_integration_runs_real_agent`) se ejecuta **solo en ARM64**, que es la arquitectura de producción. Localmente se salta por defecto vía `addopts = "-m 'not integration'"` (pyproject.toml); se ejecuta con `pytest -m integration` (el `-m` de la CLI anula el `addopts`).

Notas:

- El test de integración es hardware-agnostic: aísla BD y reportes con `tmp_path`/`monkeypatch` y degrada con gracia si falta `/sys/class/thermal`.
- Los runners ARM64 nativos de GitHub están disponibles para repositorios públicos. Si el label `ubuntu-24.04-arm` no estuviera disponible, el fallback es QEMU:

```yaml
- uses: docker/setup-qemu-action@v3
- uses: actions/setup-python@v5
  with:
    python-version: '3.11'
    architecture: 'arm64'
```
