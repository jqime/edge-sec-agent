# Operación de Edge Sec Agent (ARM64)

## Objetivo

Este documento define una ruta reproducible para desplegar y operar `edge-sec-agent` en Orange Pi / Debian ARM64 separando:

- **Código versionado:** `/opt/edge-sec-agent/app/current`
- **Configuración y secrets fuera de Git:** `/opt/edge-sec-agent/config`
- **Datos persistentes:** `/opt/edge-sec-agent/data`
- **Reportes y backups:** `/opt/edge-sec-agent/reports`, `/opt/edge-sec-agent/backups`

## Bootstrap idempotente desde cero

> Requiere root y Debian/DietPi ARM64.

```bash
sudo /opt/edge-sec-agent/app/current/scripts/bootstrap_debian_arm64.sh \
  --repo-url https://github.com/jqime/edge-sec-agent.git \
  --channel stable
```

El bootstrap valida arquitectura/memoria/espacio, crea `edgesec`, instala dependencias mínimas, prepara rutas persistentes, instala units de systemd y **no borra** datos existentes.

## Servicios systemd

Units recomendadas (en `systemd/`):

- `edge-sec-agent.service`: API Gunicorn (least privilege con `User=edgesec`)
- `edge-sec-agent-health.timer`: watchdog periódico
- `edge-sec-agent-backup.timer`: backup periódico
- `edge-sec-agent-update.timer`: actualización segura **opt-in**

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
