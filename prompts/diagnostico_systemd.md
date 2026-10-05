# DIAGNÓSTICO Y REPARACIÓN DE SYSTEMD

Analiza exclusivamente el arranque de los servicios del proyecto.

Servicios objetivo:

- `ollama`
- `edge-sec-agent`
- `nginx`
- `fail2ban`

No modifiques firewall ni SSH en esta fase.

Para cada servicio:

1. Ejecuta:
   ```bash
   systemctl status SERVICIO --no-pager
   systemctl is-enabled SERVICIO
   journalctl -u SERVICIO -n 150 --no-pager
   ```
2. Identifica:
   - código de salida;
   - dependencia ausente;
   - ruta incorrecta;
   - usuario incorrecto;
   - permisos;
   - variable de entorno;
   - puerto ocupado;
   - archivo de configuración inválido.
3. Comprueba la unidad real con:
   ```bash
   systemctl cat SERVICIO
   ```
4. Crea backup antes de modificar una unidad.
5. Valida con:
   ```bash
   systemd-analyze verify /etc/systemd/system/edge-sec-agent.service
   ```
6. Ejecuta:
   ```bash
   systemctl daemon-reload
   systemctl restart SERVICIO
   ```
7. Verifica que queda activo.
8. Registra todo en `AGENTS.md`.

No declares un servicio reparado hasta que:
- esté `active`;
- esté `enabled` si corresponde;
- sobreviva a un reinicio o quede explícitamente `NO VERIFICADO`;
- sus logs no muestren errores de arranque.
