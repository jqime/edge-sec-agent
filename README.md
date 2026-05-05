# 🦞 Edge Sec Agent

<p align="center">
  <img src="https://img.icons8.com/color/96/000000/security-checked--v1.png" width="80"/>
  <br/>
  <strong>Agente DevSecOps autónomo para Orange Pi Zero 3</strong><br/>
  <em>Monitorización, hardening y respuesta a incidentes — sin cloud, sin GPU, sin excusas.</em>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white"/></a>
  <a href="https://ollama.com/"><img src="https://img.shields.io/badge/Ollama-Local-brightgreen"/></a>
  <a href="http://www.orangepi.org/"><img src="https://img.shields.io/badge/Orange%20Pi-Zero%203-orange"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green"/></a>
  <a href="https://github.com/jqime/edge-sec-agent/releases"><img src="https://img.shields.io/badge/Release-v1.0-blue"/></a>
  <a href="https://github.com/jqime/edge-sec-agent/stargazers"><img src="https://img.shields.io/github/stars/jqime/edge-sec-agent?style=social"/></a>
</p>

---

## ¿Qué es?

**Edge Sec Agent** es un asistente DevSecOps que corre **100% en local** sobre una Orange Pi Zero 3 (ARM, 4 GB RAM). No necesita cloud, API keys ni GPU.

Combina tres capas complementarias:

- **Comandos instantáneos** — información del sistema en menos de 1 segundo.
- **Planificador por reglas** — tareas comunes de seguridad sin esperar a la IA.
- **IA local con Ollama** — análisis conversacional para preguntas complejas.

Junto con herramientas MCP extensibles, alertas por Telegram, API REST y soporte opcional para OpenWebUI, cubre desde el hardening inicial hasta la respuesta a incidentes en producción.

---

## Capacidades

| Módulo | Función | Latencia | IA |
|---|---|---|---|
| `sec` | Comandos rápidos del sistema | < 1 s | No |
| `sec-chat --plan` | Reglas de seguridad predefinidas | < 2 s | No |
| `sec-chat --tool` | Herramientas MCP extensibles | < 2 s | No |
| `sec-agent` | Selector automático reglas/IA | < 2 s / 10–90 s | Opcional |
| `ia` | IA conversacional directa | 10–90 s | Sí |
| API REST | Integración externa vía HTTP | < 1 s | No |

---

## Arquitectura

```
Usuario
   │
   ├── sec            → comandos del SO (<1s)
   ├── sec-chat       → reglas + herramientas MCP (<2s)
   ├── sec-agent      → selector automático
   └── ia             → modelos locales vía Ollama
                            │
                            └── Sistema (logs, red, procesos, firewall)
```

Todo se ejecuta en la Orange Pi Zero 3. Nada sale de la red local.

---

## Instalación

### Requisitos previos

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:0.5b
```

### Clonar e instalar

```bash
git clone https://github.com/jqime/edge-sec-agent.git
cd edge-sec-agent
cp scripts/sec scripts/sec-chat scripts/sec-agent scripts/ia /usr/local/bin/
chmod +x /usr/local/bin/sec /usr/local/bin/sec-chat /usr/local/bin/sec-agent /usr/local/bin/ia
```

### Verificar

```bash
sec status
sec-chat --plan "fallos ssh"
ia "hola"
```

---

## Uso

### `sec` — información del sistema en tiempo real

```bash
sec status      # IP, RAM, CPU, puertos abiertos, fallos SSH
sec red         # dispositivos en la red local (ARP)
sec puertos     # puertos en escucha
sec procesos    # procesos con mayor consumo de CPU
sec temp        # temperatura del procesador
sec ram         # uso de memoria
```

### `sec-agent` — selector automático (recomendado para uso diario)

Detecta si la consulta es operativa (reglas rápidas) o conversacional (IA).

```bash
sec-agent "estado del sistema"           # reglas: < 2 s
sec-agent "¿cómo mejorar la seguridad?"  # IA: 10–90 s
```

### `ia` — IA conversacional directa

```bash
ia "¿qué puertos están abiertos?"
ia "dame recomendaciones de hardening SSH"
```

### `sec-chat` — planificador por reglas y herramientas MCP

**Modo reglas (`--plan`):**

```bash
sec-chat --plan "fallos ssh"
sec-chat --plan "estado del firewall"
sec-chat --plan "escanear puertos localhost"
sec-chat --plan "bloquear ip 192.168.1.100"
```

Reglas disponibles: `fallos ssh`, `estado del firewall`, `actualizar paquetes`, `fail2ban status`, `reiniciar docker`, `escanear puertos localhost`, `bloquear ip <IP>`.

**Herramientas MCP (`--tool`):**

```bash
sec-chat --tool security-score      # puntuación de seguridad 0–100
sec-chat --tool forensic-snapshot   # instantánea forense del sistema
sec-chat --tool audit               # auditoría de seguridad
sec-chat --tool harden              # hardening básico
sec-chat --tool ir-response isolate # aislar la red ante un incidente
sec-chat --tool custom-report daily # informe diario
```

| Herramienta | Función |
|---|---|
| `security-score` | Puntuación 0–100 basada en UFW, fail2ban y SSH |
| `forensic-snapshot` | Procesos, conexiones, logins y archivos recientes |
| `audit` | Fallos SSH, sudo y servicios expuestos |
| `harden` | IPv6, MaxAuthTries, puertos innecesarios |
| `event-correlator` | Correlación de eventos: SSH, CPU, conexiones |
| `ir-response` | `isolate` / `lockdown <puerto>` / `status` |
| `custom-report` | Informes `daily` o `weekly` |
| `backup` | Respaldo de SSH, UFW y fail2ban |
| `vuln-scan` | Escaneo rápido con Lynis |

**Herramientas personalizadas:** añade un script ejecutable en `~/mcp_tools/` y ejecútalo con `sec-chat --tool <nombre>`.

---

## Ejemplo real: detección y respuesta a ataque SSH

```bash
# 1. Cron detecta > 5 fallos SSH → alerta a Telegram
# 2. Revisar los intentos
sec-chat --plan "fallos ssh"

# 3. Tomar instantánea forense
sec-chat --tool forensic-snapshot

# 4. Aislar si es necesario
sec-chat --tool ir-response isolate

# 5. Pedir análisis a la IA
ia "tengo muchos fallos SSH desde la misma IP, ¿qué hago?"
```

---

## API REST

Servicio activo en el puerto `8765` mediante systemd (`sec-api.service`).

```bash
curl -X POST http://localhost:8765/ask \
  -H "Content-Type: application/json" \
  -d '{"pregunta": "status"}'
```

Respuesta:

```json
{"respuesta": "IP 192.168.1.141 | RAM 1.9Gi/3.8Gi | Temp 34.1C | Puertos 22 8765 11434 | Fallos SSH 2"}
```

---

## Generación de informes de seguridad

- Uso del comando `sec-agent --security`:
  - Ejecuta cmd_security para generar el informe de seguridad y guardarlo en REPORTS_DIR (por defecto /root/edge-sec-agent/reports). Si se invoca con `--json`, imprime la salida en formato JSON y no genera el informe en texto ni guarda el archivo.
- Explicación de la puntuación (qué factores se evalúan y cómo se ponderan):
  - Fallos SSH: cuenta de intentos fallidos a partir de los logs SSH. Contribuye hasta 60 puntos de penalización.
  - Puertos abiertos: cuentan puertos en escucha que no están en la lista permitida (22, 80, 443, 25, 53). Cada puerto fuera de la lista penaliza hasta 40 puntos.
  - Temperatura CPU: si la temperatura supera 55C, añade penalización (hasta 25 puntos).
  - RAM usada: si el uso supera 60%, añade penalización (hasta 25 puntos).
  - Puntuación final = 100 - int(penalizaciones). Resultado entre 0 y 100.
- Dónde se guardan los informes y cómo personalizar la ruta (variable `REPORTS_DIR`):
  - Informe guardado en REPORTS_DIR, por defecto /root/edge-sec-agent/reports.
  - Puedes configurar la ruta creando la variable de entorno REPORTS_DIR (por ejemplo en /etc/edge-sec-agent/sec-report.env o en tu entorno de servicio).
- Ejemplo de salida:
  - Texto:
  ```text
  Informe de Seguridad - Puntuación: 78/100
  Riesgos detectados:
  - SSH: fallos observados = 3
  - Puertos abiertos: 22, 80, 9999
  - Temperatura CPU: 55.3C
  - RAM usado: 68.4%
  Recomendaciones específicas:
    - SSH: usar autenticación por clave, deshabilitar root y login por contraseña, activar fail2ban o similares.
    - Puertos abiertos: cerrar servicios no esenciales, usar firewall para limitar acceso.
    - RAM alta utilización: optimizar procesos, considerar swap/zram, revisar fuga de memoria.
  Informe guardado en: /root/edge-sec-agent/reports/security_20240504-123456.txt
  ```
  - JSON con `--json` (la ruta de informe no se genera en este modo, report_path = null):
  ```json
  {"score":78,"ssh_failures":3,"open_ports":["22","80","9999"],"temp_c":55.3,"ram_percent":68.4,"report_path":null}
  ```
- Automatización (cron o systemd timer):
  - Systemd (recomendado): usar sec-report.service y sec-report.timer creados en pasos anteriores.
    - comandos:
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable sec-report.timer
    sudo systemctl start sec-report.timer
    sudo systemctl status sec-report.timer
    ```
  - Cron (alternativa):
    ```bash
    0 */12 * * * /usr/local/bin/report-cron.sh
    ```
    Este script genera el informe y, si está configurado, envía el correo y registra en /var/log/edge-sec-report.log.
- Notas:
  - Si ALERT_EMAIL no está configurado, no se enviarán correos.
  - REPORTS_DIR es configurable a través de la variable de entorno; si se cambia, el script lo respeta y crea el directorio si no existe.

## Monitorización automática

El agente instala tareas cron que ejecutan automáticamente:

- Cada **10 minutos** — alerta si hay más de 5 fallos SSH.
- Cada **5 minutos** — alerta si la temperatura supera 60 °C.
- Cada **hora** — informe completo del estado del sistema.

Las alertas se envían por Telegram. Para revisar el histórico:

```bash
grep "sec" /var/log/syslog
```

---

## OpenWebUI (opcional)

Interfaz web para interactuar con los modelos Ollama desde el navegador.

```bash
docker run -d --name openwebui \
  --add-host host.docker.internal:host-gateway \
  -p 3000:8080 --restart unless-stopped \
  ghcr.io/open-webui/open-webui:main
```

Acceso: `http://192.168.1.141:3000`

---

## Rendimiento en Orange Pi Zero 3

| Operación | Tiempo |
|---|---|
| `sec status` | < 1 s |
| `sec-chat --plan` | < 2 s |
| Herramienta MCP | < 2 s |
| `ia` con `qwen2.5:0.5b` | 10–20 s |
| `ia` con `qwen2.5:3b` | 60–90 s |

La IA es lenta por el hardware (ARM sin GPU). Para el trabajo diario, los comandos rápidos y las reglas son más que suficientes.

---

## Seguridad

- Todo el código y los modelos se ejecutan **localmente**. Ningún dato sale de la red.
- Comandos destructivos bloqueados (`rm`, `dd`, `mkfs`, `shutdown`, etc.).
- Las herramientas MCP se ejecutan **sin privilegios elevados**.
- La API REST no ejecuta comandos arbitrarios.
- La IA está aislada del shell.
- Se recomienda fail2ban activo y cambio del puerto SSH por defecto.

---

## Configuración

El agente se configura mediante variables de entorno:

| Variable | Valor por defecto | Descripción |
|---|---|---|
| `EDGE_MODEL` | `qwen2.5:0.5b` | Modelo Ollama |
| `EDGE_MAX_TOKENS` | `120` | Tokens máximos por respuesta |
| `EDGE_TIMEOUT` | `180` | Timeout en segundos |

---

## Estructura del proyecto

```
edge-sec-agent/
├── src/
│   └── agent.py           # Agente principal con OpenRouter/Ollama
├── scripts/
│   ├── sec                # Comandos rápidos del sistema
│   ├── sec-chat           # Planificador + herramientas MCP
│   ├── sec-agent          # Selector automático
│   ├── ia                 # IA conversacional directa
│   └── sec-api            # Servidor REST
├── mcp_tools/             # Herramientas MCP extensibles
│   ├── security-score
│   ├── forensic-snapshot
│   ├── audit
│   ├── harden
│   ├── ir-response
│   ├── event-correlator
│   ├── custom-report
│   ├── backup
│   └── vuln-scan
├── docs/
│   ├── SETUP.md
│   └── ARCHITECTURE.md
└── sec-api.service        # Unidad systemd para la API REST
```

---

## Roadmap

- [x] Comandos rápidos (`sec`)
- [x] Planificador por reglas (`sec-chat --plan`)
- [x] Herramientas MCP (`sec-chat --tool`)
- [x] Monitorización automática con alertas Telegram
- [x] OpenWebUI como interfaz web opcional
- [x] API REST (`sec-api`)
- [x] Selector automático (`sec-agent`)
- [x] IA conversacional local (`ia`)
- [ ] Modo demonio con alertas personalizables (`sec-daemon`)
- [ ] Soporte multi-modelo vía `EDGE_MODEL`
- [ ] Dashboard web con métricas en tiempo real

---

## Contribuir

Las contribuciones son bienvenidas. Para añadir una herramienta MCP, crea un script ejecutable en `mcp_tools/`, pruébalo con `sec-chat --tool <nombre>` y abre un PR.

Para bugs o mejoras, abre un issue indicando el comando afectado y el output obtenido.

---

## Licencia

MIT © [Jaime Muñoz](https://github.com/jqime) — SecDevOps @ CDS Race Experience

---

<p align="center">
  <sub>Hecho con ❤️ para la comunidad DevSecOps en el borde — sin cloud, sin GPU, sin excusas.</sub>
</p>

## 📊 Dashboard web

## 📊 Dashboard web
Accede al dashboard en tiempo real en: http://192.168.1.141:8080
