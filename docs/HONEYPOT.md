# Cowrie SSH Honeypot

Honeypot SSH aislado que captura intentos de acceso, credenciales y comandos de atacantes, y notifica por Telegram. Base para un futuro análisis con RAG.

## Estado

- Servicio: `cowrie.service` (systemd) — `active`, `enabled`.
- Escucha: `0.0.0.0:2223` (puerto dedicado; **no** toca `2222` Dropbear ni `5000` API).
- Usuario: `cowrie` (uid 993, cuenta bloqueada, sin privilegios).
- Directorio: `/opt/cowrie/cowrie-git` (checkout) + `/opt/cowrie/venv` (entorno Python).
- Versión Cowrie: `0.1.dev1+gc7773f497` · Twisted 26.4.0 · Python 3.13.5.

## Aislamiento (principio de mínimo privilegio)

```
Atacante ──▶ :2223 ──▶ cowrie.service (User=cowrie, sin root)
                         │
                         └─▶ /opt/cowrie/cowrie-git/var/log/cowrie/cowrie.json
                                      │
                          scripts/cowrie_alert.sh (User=edgesec)
                                      │
                                      └─▶ Telegram (TELEGRAM_BOT_TOKEN / CHAT_ID)

Producción (intacta): Dropbear :2222 (tailscale0) · Gunicorn :5000 (loopback) · Nginx :8443
```

Cowrie **no** comparte usuario, directorio ni puerto con el agente principal. El firewall no se ha modificado: con la política actual, `2223` queda alcanzable en LAN y Tailscale (y por Internet solo si el router reenvía).

## Configuración

Fichero: `/opt/cowrie/cowrie-git/etc/cowrie.cfg` (override de operador, generado con `cowrie init`).

| Ajuste | Valor | Nota |
|---|---|---|
| `[ssh] listen_endpoints` | `tcp:2223:interface=0.0.0.0` | Cambiado desde el default 2222 |
| `[ssh] enabled` | `true` | |
| `[telnet] enabled` | `false` | Sin conflicto de puerto |
| `[output_jsonlog] enabled` | `true` | Log JSON |
| `[output_jsonlog] logfile` | `${honeypot:log_path}/cowrie.json` | → `var/log/cowrie/cowrie.json` |
| `hostname` | `svr04` | Señuelo |

### Credenciales falsas (`etc/userdb.txt`)

```
root:x:123456
root:x:password
root:x:toor
admin:x:admin
admin:x:123456
user:x:user
```

Formato Cowrie `usuario:x:password` (el campo `x` se ignora). Estas credenciales **no** existen en el sistema real; solo permiten que Cowrie conceda una shell falsa y registre `cowrie.command.input`.

## Logs

- Ruta: `/opt/cowrie/cowrie-git/var/log/cowrie/cowrie.json` (una línea JSON por evento).
- Eventos relevantes: `cowrie.session.connect`, `cowrie.login.failed`, `cowrie.login.success`, `cowrie.command.input`.

Leer los últimos eventos:

```bash
tail -n 5 /opt/cowrie/cowrie-git/var/log/cowrie/cowrie.json | python3 -m json.tool --json-lines
```

Resumen por tipo de evento:

```bash
python3 - <<'PY'
import json, collections
c = collections.Counter()
for line in open('/opt/cowrie/cowrie-git/var/log/cowrie/cowrie.json'):
    line = line.strip()
    if line:
        try:
            c[json.loads(line).get('eventid')] += 1
        except ValueError:
            pass
print(dict(c))
PY
```

## Alertas (`scripts/cowrie_alert.sh`)

- Ejecuta como `edgesec`; lee secretos de `SECRETS_PATH` o `<repo>/secrets.env` (fuera de Git, modo 600).
- Guarda el offset de lectura en `data/cowrie_alert.state` (solo procesa eventos nuevos; reinicia a 0 si el log rota).
- Anti-spam: `data/cowrie_alert.seen` suprime repetidos por IP dentro de `COWRIE_ALERT_SUPPRESS` segundos (por defecto 300).
- Lock con `flock` para evitar ejecuciones concurrentes.
- Variables: `COWRIE_LOG`, `COWRIE_ALERT_STATE_DIR`, `COWRIE_ALERT_SUPPRESS`, `SECRETS_PATH`, `COWRIE_ALERT_DEBUG=1` (imprime la respuesta de Telegram).

Uso manual:

```bash
sudo -u edgesec /opt/edge-sec-agent/scripts/cowrie_alert.sh
```

## Verificación realizada

| Comprobación | Evidencia |
|---|---|
| Servicio activo | `systemctl is-active cowrie` → `active` |
| Escucha en 2223 | `ss -tlnp` → `0.0.0.0:2223` (twistd) |
| Captura de intento | `cowrie.login.failed` en `cowrie.json` |
| Captura de comando | `cowrie.login.success` + `cowrie.command.input` |
| Anti-spam | 15 eventos → 1 alerta; eventos nuevos mismos IP → suprimidos |
| Telegram | respuesta API `{"ok":true, message_id:1328}` |

## Limitaciones y próximos pasos

- **Sin timer**: las alertas solo se envían cuando se ejecuta `cowrie_alert.sh`. Pendiente de autorización añadir `cowrie-alert.timer` (p. ej. cada 60 s).
- **Endpoint `/api/honeypot`** (opcional) no implementado: requeriría tocar `src/sec_web.py` (código de producción).
- **Endurecimiento systemd**: la unit es funcional pero no incluye `ProtectSystem`/`ProtectHome`/`NoNewPrivileges`.
- **Persistencia en reinicio**: `cowrie.service` está `enabled`, pero el firewall no tiene regla para `2223` (por diseño, sin tocar firewall).
- **Bloat/espacio**: el checkout + venv ocupan espacio en `/opt`; sin swap activo (decisión del owner).
