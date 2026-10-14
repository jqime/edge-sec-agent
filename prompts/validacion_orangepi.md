# VALIDACIÓN END-TO-END DE LA ORANGE PI

La configuración ya ha sido aplicada. No realices cambios destructivos.

Comprueba el estado completo del sistema:

```bash
systemctl --failed --no-pager
systemctl is-active ollama
systemctl is-active edge-sec-agent
systemctl is-active nginx
systemctl is-active fail2ban
ss -tlnp
free -h
df -h
```

Comprueba la aplicación:

```bash
curl -fsS http://127.0.0.1:5000/
curl -fsS http://127.0.0.1:5000/v1/global/health
curl -fsS http://127.0.0.1:5000/metrics
curl -fsS http://127.0.0.1:5000/api/metrics
curl -fsS http://127.0.0.1:5000/v1/models
```

Comprueba Nginx:

```bash
nginx -t
curl -k -I https://127.0.0.1:8443/
curl -k -I https://127.0.0.1:8443/health
curl -k -I https://127.0.0.1:8443/metrics
```

Comprueba Fail2Ban:

```bash
fail2ban-client ping
fail2ban-client status
fail2ban-client status sshd
fail2ban-client status nginx-http-auth
```

Comprueba Ollama:

```bash
curl -fsS http://127.0.0.1:11434/api/tags
ollama list
```

Registra cada resultado en `AGENTS.md`.

No cambies configuraciones durante esta fase salvo que encuentres un fallo crítico. Si encuentras un fallo, regístralo y crea un plan separado.
