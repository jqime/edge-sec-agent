# Runbook de recuperación total (Orange Pi / Debian ARM64)

## 1) Reinstalar SO y red base

1. Instalar Debian/DietPi ARM64.
2. Configurar red/SSH de forma manual y segura.
3. Validar acceso remoto (idealmente por Tailscale + puerto SSH alternativo).

## 2) Clonar repositorio

```bash
git clone https://github.com/jqime/edge-sec-agent.git /opt/edge-sec-agent/app/current
cd /opt/edge-sec-agent/app/current
```

## 3) Restaurar configuración/secrets fuera de Git

- Restaurar `/opt/edge-sec-agent/config/edge-sec-agent.env` desde un backup seguro.
- Restaurar credenciales TLS/Basic Auth fuera del repositorio.

## 4) Ejecutar bootstrap

```bash
sudo ./scripts/bootstrap_debian_arm64.sh --channel stable
```

## 5) Restaurar datos persistentes

```bash
sudo ./scripts/restore_state.sh /opt/edge-sec-agent/backups/<timestamp>
```

## 6) Validar salud y servicios

```bash
systemctl --failed --no-pager
systemctl status edge-sec-agent edge-sec-agent-backup.timer edge-sec-agent-health.timer --no-pager
curl --fail --silent http://127.0.0.1:5000/v1/global/health
curl --fail --silent http://127.0.0.1:5000/metrics
```

## 7) Volver a producción

1. Verificar reverse proxy + TLS + Basic Auth en Nginx.
2. Verificar que backend y Ollama no estén expuestos públicamente.
3. Habilitar update timer solo si está validado (`/etc/edge-sec-agent/update.enabled`).

## 8) Política de firewall

Esta entrega **no aplica** cambios automáticos de firewall.
Aplicar reglas sólo con procedimiento explícito, backup previo y rollback probado.
