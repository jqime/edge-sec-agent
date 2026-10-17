# Cowrie SSH Honeypot

Honeypot SSH aislado que captura intentos de acceso, credenciales y comandos de atacantes, y notifica por Telegram. Base para un futuro análisis con RAG.

## Estado

- Servicio: `cowrie.service` (systemd) — `active`, `enabled`.
- Escucha: `0.0.0.0:2223` (puerto dedicado; **no** toca `2222` Dropbear ni `5000` API). Acceso entrante restringido por firewall a la interfaz `tailscale0` (ver *Aislamiento*).
- Usuario: `cowrie` (uid 993, cuenta bloqueada, sin privilegios).
- Directorio: `/opt/cowrie/cowrie-git` (checkout) + `/opt/cowrie/venv` (entorno Python).
- Versión Cowrie: `0.1.dev1+gc7773f497` · Twisted 26.4.0 · Python 3.13.5.
- Alertas: `cowrie-alert.timer` → `cowrie-alert.service` (cada 60 s) ejecuta `scripts/cowrie_alert.sh`.
- Endurecimiento systemd: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome=true`, `ProtectKernelTunables`, `ProtectControlGroups`, `RestrictRealtime`, `ReadWritePaths=/opt/cowrie/cowrie-git/var`.

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

Cowrie **no** comparte usuario, directorio ni puerto con el agente principal. El puerto `2223` está restringido por firewall (unit `edge-firewall`, `scripts/apply_firewall.sh`): solo se acepta tráfico entrante por la interfaz `tailscale0`; en cualquier otra interfaz (loopback, LAN, WAN) se descarta. Reglas espejo IPv4 + IPv6:

```
-A INPUT -i tailscale0 -p tcp --dport 2223 -j ACCEPT
-A INPUT -p tcp --dport 2223 -j DROP
```

Así, aunque el listener siga siendo `0.0.0.0:2223`, el honeypot solo es alcanzable desde la tailnet. Si la Pi se conecta a una red wifi pública, el puerto no queda visible para el resto de esa red.

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

> **Importante:** `userdb.txt` se lee con encoding **ASCII** (`cowrie/core/auth.py`). Cualquier carácter no-ASCII (p. ej. un guion largo `—`) provoca un `UnicodeDecodeError` y rompe toda la autenticación. Mantener el fichero en ASCII puro.

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
| Acceso a 2223 | `iptables -S INPUT \| grep 2223` → `ACCEPT` en `tailscale0` + `DROP`; conexión a `127.0.0.1:2223` / `192.168.1.141:2223` → timeout (bloqueado) |
| Captura de intento | `cowrie.login.failed` en `cowrie.json` |
| Captura de comando | `cowrie.login.success` + `cowrie.command.input` |
| Anti-spam | 15 eventos → 1 alerta; eventos nuevos mismos IP → suprimidos |
| Telegram | respuesta API `{"ok":true, message_id:1328}` |
| Timer automático | `cowrie-alert.timer` active/enabled; oneshot `status=0/SUCCESS`; próxima ejecución programada |
| Tras endurecimiento | login falso + `cowrie.command.input` siguen capturándose; `systemd-analyze verify` exit 0 |
| Exposición systemd | `systemd-analyze security cowrie.service` → 7.9 EXPOSED (honeypot emula sistema completo) |

## Evidencia de Captura (Entorno Controlado)

Análisis completo del log `cowrie.json` en el rango `2026-10-17T20:50:39Z` → `2026-10-17T21:48:19Z` (~1 h). Tres orígenes, **ninguno público**:

| Origen | Clasificación | Eventos |
|---|---|---|
| `127.0.0.1` | Pruebas internas (`sshpass`) desde la Pi | 47 |
| `100.109.41.91` | Portátil Windows del owner vía Tailscale ("jaime") | 12 |
| `100.125.181.114` | IP Tailscale de la propia Orange Pi (autoprueba local) | 12 |

Ciclo observado desde `100.109.41.91` (2026-10-17 21:04:58Z → 21:08:25Z UTC):

```
session.connect
  -> client.version   (SSH-2.0-OpenSSH_for_Windows_9.5)
  -> client.fingerprint (51:fc:78:46:7d:54:1e:a3:30:64:a2:1f:f8:2c:cf:9c)
  -> login.failed     (usuario: root)
  -> login.success    (usuario: root, password: 123456)
  -> command.input    ("ls -la")
  -> command.input    ("whoami")
  -> session.closed
```

**Lección técnica (fingerprinting):** Cowrie capturó el *banner* del cliente SSH (`SSH-2.0-OpenSSH_for_Windows_9.5`) y el fingerprint de la clave del cliente. Es decir, además del usuario/contraseña, registra la huella del software y del host que se conecta: `OpenSSH_for_Windows_9.5` identifica un cliente Windows, no un bot Linux.

Muestra del formato de alerta recibida en Telegram (texto, sin secretos):

```
Honeypot Cowrie - amenaza detectada
Evento: cowrie.login.success
Origen: 100.109.41.91
Detalle: root
Hora: 2026-10-17T21:05:16Z
Sensor: Orange Pi Zero 3 (:2223)
```

### Nota de honestidad técnica (qué es y qué no es)

`100.109.41.91` y `100.125.181.114` pertenecen al rango CGNAT de Tailscale (`100.64.0.0/10`); **no es tráfico de Internet**. El primero es el portátil del owner y el segundo la propia Pi (confirmado con `tailscale ip -4`). En el log **no aparece ninguna IP pública**, por lo que **aún no se ha capturado tráfico de Internet real**: el puerto `2223` no está expuesto en el router (no hay port-forwarding), y ahora además está restringido a `tailscale0` por firewall. Capturar escaneos de Internet exigiría reenviar el puerto en el router (decisión de red del owner, no aplicada).

## Limitaciones y próximos pasos

- **Endpoint `/api/honeypot`** (opcional) no implementado: requeriría tocar `src/sec_web.py` (código de producción).
- **Exposición systemd 7.9**: podría bajarse con `RestrictAddressFamilies`, `SystemCallFilter` o `MemoryDenyWriteExecute`, con riesgo de romper Cowrie; pendiente de validación por etapas.
- **Acceso al puerto**: `2223` está restringido a `tailscale0` por `edge-firewall` (aplicado y validado). Solo peers de la tailnet pueden alcanzar el honeypot.
- **Bloat/espacio**: el checkout + venv ocupan espacio en `/opt`; sin swap activo (decisión del owner).
