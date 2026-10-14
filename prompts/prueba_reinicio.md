# PRUEBA DE PERSISTENCIA TRAS REINICIO

Antes de reiniciar:

1. Verifica que `nginx -t` pasa.
2. Verifica que Fail2Ban tiene configuración válida.
3. Verifica que el acceso SSH por el puerto administrativo funciona.
4. Registra el estado actual en `AGENTS.md`.
5. Comprueba que existen backups y rollback.

Después ejecuta el reinicio únicamente si todas las comprobaciones anteriores pasan.

Tras volver a conectar:

```bash
uptime
systemctl --failed --no-pager
systemctl is-active ollama
systemctl is-active edge-sec-agent
systemctl is-active nginx
systemctl is-active fail2ban
ss -tlnp
curl -fsS http://127.0.0.1:5000/v1/global/health
curl -fsS http://127.0.0.1:5000/metrics
curl -k -I https://127.0.0.1:8443/
```

Comprueba también:

```bash
systemctl is-enabled ollama
systemctl is-enabled edge-sec-agent
systemctl is-enabled nginx
systemctl is-enabled fail2ban
```

Solo marca la prueba como `COMPLETADA` si los servicios vuelven automáticamente y los endpoints responden.
