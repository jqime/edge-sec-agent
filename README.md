# Edge Security Agent

**Agente de monitoreo y endurecimiento perimetral para nodos Edge/IoT**

Plataforma DevSecOps de producción diseñada para dispositivos embebidos basados en **DietPi / Debian 12** sobre hardware **Orange Pi Zero 3** (ARM, 4GB RAM). Proporciona visibilidad de seguridad en tiempo real, análisis automatizado de vectores de ataque, herramientas de diagnóstico extensibles (MCP), dashboard web con métricas compatibles con Prometheus y endurecimiento activo del sistema operativo.

---

## Arquitectura de Infraestructura

### Flujo de Datos

```
┌─────────────────────────────────────────────────────────────────────┐
│                        RED LOCAL (192.168.1.0/24)                   │
│                                                                     │
│  [Tráfico Externo] ───────────────────────────────────────────┐     │
│                                                               │     │
│                                                               ▼     │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  NGINX REVERSE PROXY                                            ││
│  │  Bind: 0.0.0.0:8080                                             ││
│  │  - client_max_body_size: 10M                                    ││
│  │  - Rutas: /, /api/metrics, /v1/global/health, /metrics          ││
│  │  - Logging: /var/log/nginx/edge-sec-agent-*.log                 ││
│  └────────────────────────────┬────────────────────────────────────┘│
│                               │ proxy_pass                          │
│                               ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  GUNICORN WSGI SERVER                                           ││
│  │  Bind: 127.0.0.1:5000 (SOLO LOOPBACK)                           ││
│  │  - Workers: 2  |  Timeout: 120s  |  Restart: always             ││
│  │  - Entry point: wsgi:app                                        ││
│  │  - Logs: /var/log/gunicorn-edge-*.log                           ││
│  └────────────────────────────┬────────────────────────────────────┘│
│                               │                                     │
│                               ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  FLASK APPLICATION (src/sec_web.py)                             ││
│  │  - Endpoints RESTful                                            ││
│  │  - Integración con MCP Tools                                    ││
│  │  - Lectura de métricas del sistema en tiempo real               ││
│  └────┬──────────────────────┬──────────────────────┬──────────────┘│
│       │                      │                      │               │
│       ▼                      ▼                      ▼               │
│  ┌──────────┐          ┌──────────┐          ┌──────────────┐       │
│  │ SQLite   │          │ MCP      │          │ System       │       │
│  │ Database │          │ Tools    │          │ Commands     │       │
│  │ (metrics)│          │ (bash)   │          │ (ss, iptables│       │
│  │          │          │          │          │  fail2ban)   │       │
│  └──────────┘          └──────────┘          └──────────────┘       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  CAPA DE ACCESO REMOTO SEGURO                                       │
│                                                                     │
│  [SSH Client] ──► Dropbear SSH (Port 2222) ──► Shell Root          │
│                                                                     │
│  Puerto 22: BLOQUEADO por iptables (IPv4 + IPv6 DROP)               │
│  Puerto 2222: ÚNICO punto de acceso SSH autorizado                  │
└─────────────────────────────────────────────────────────────────────┘
```

### Aislamiento Perimetral

La arquitectura implementa un modelo de **defensa en profundidad** con tres capas de aislamiento:

1. **Capa de red (Nginx)**: Único servicio expuesto a `0.0.0.0:8080`. Actúa como escudo inverso, filtrando peticiones malformadas, limitando tamaño de cuerpo a 10MB y registrando toda la actividad.

2. **Capa de aplicación (Gunicorn/Flask)**: Vinculado exclusivamente a `127.0.0.1:5000`. Inaccesible desde cualquier interfaz de red externa. Solo Nginx puede comunicarse con él mediante loopback.

3. **Capa de acceso remoto (Dropbear)**: El demonio SSH original en puerto 22 ha sido deshabilitado a nivel de configuración del demonio y bloqueado adicionalmente por reglas de firewall `iptables`. El acceso SSH solo es posible mediante el puerto alternativo `2222`, reduciendo la superficie de ataque ante escaneos automatizados.

---

## Matriz de Puertos y Hardening

### Estado de Puertos: Antes vs Después

| Puerto | Servicio Original | Estado Actual | Tipo de Exposición | Mitigación Aplicada |
|:------:|:------------------|:--------------|:-------------------|:--------------------|
| **22** | Dropbear SSH | **BLOQUEADO** (iptables DROP) | Ninguna | Desactivación en `/etc/default/dropbear` (`DROPBEAR_PORT=2222`). Regla `iptables -I INPUT -p tcp --dport 22 -j DROP` aplicada para IPv4 e IPv6. |
| **2222** | Dropbear SSH | **ACTIVO** | Acceso Seguro | Puerto alternativo configurado como único punto de entrada SSH. No expuesto a internet. Acceso restringido a red local `192.168.1.0/24`. |
| **5000** | Flask Backend (Gunicorn) | **AISLADO** (127.0.0.1) | Interno | Vinculado exclusivamente a interfaz loopback. Inaccesible desde cualquier interfaz de red física o virtual. Solo proxy Nginx puede conectar. |
| **8080** | Nginx Reverse Proxy | **ACTIVO** (0.0.0.0) | Público Controlado | Único servicio expuesto. Actúa como escudo inverso con limitación de cuerpo (10M), logging completo y timeout configurados. |

### Resumen de Superficie de Ataque

| Métrica | Antes | Después | Reducción |
|:--------|:------|:--------|:----------|
| Puertos expuestos | 3 (22, 2222, 8080) | 1 (8080) | **66%** |
| Puertos SSH activos | 2 (22, 2222) | 1 (2222) | **50%** |
| Servicios en 0.0.0.0 | 2 | 1 | **50%** |
| Reglas firewall activas | 0 | 2 (IPv4 + IPv6 DROP :22) | **+2** |

---

## Política de Retención de Datos

### Contexto Edge/IoT

Los dispositivos embebidos como la **Orange Pi Zero 3** operan sobre almacenamiento **MicroSD**, un medio con limitaciones críticas:

- **Ciclos de escritura finitos**: Las tarjetas MicroSD típicas soportan entre 1.000 y 10.000 ciclos P/E (Program/Erase). La escritura continua sin control degrada el medio y provoca corrupción física irreversible.
- **Capacidad limitada**: Instalaciones típicas de 8-16GB donde el sistema operativo y aplicaciones ya consumen el 60-70%.
- **Sin alertas de espacio**: A diferencia de servidores enterprise, los nodos edge rara vez tienen monitorización proactiva de almacenamiento.

### Implementación: `prune_old_metrics(days=30)`

El módulo `src/database.py` implementa una política de retención automática que protege la integridad del almacenamiento:

```python
def prune_old_metrics(days=30):
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_conn()
    deleted = conn.execute("DELETE FROM metrics WHERE timestamp < ?", (cutoff,)).rowcount
    conn.commit()
    conn.close()
    return deleted
```

**Comportamiento**:
- Se invoca **automáticamente** cada vez que se inicializa la base de datos (`init_db()`), lo que ocurre en cada arranque del servicio y en cada importación del módulo.
- Elimina todos los registros de la tabla `metrics` con `timestamp` anterior a 30 días.
- Retorna el número de registros eliminados (útil para auditoría).
- El parámetro `days` es configurable por defecto a 30 días, equilibrando historial útil con espacio en disco.

**Impacto estimado**:
- Con una métrica cada 5 minutos: ~8.640 registros/mes → ~259.200 registros a retener.
- Sin retención: crecimiento ilimitado hasta llenar la partición `/root`.
- Con retención a 30 días: tamaño estable de la base de datos (~15-25MB).

---

## Guía de Despliegue en un Solo Paso

### Requisitos Previos

| Requisito | Detalle |
|:----------|:--------|
| **Hardware** | Orange Pi Zero 3 (ARM64, 4GB RAM) o compatible |
| **Sistema Operativo** | DietPi / Debian 12 (Bookworm) |
| **Acceso** | Root via SSH (puerto 22 o 2222) |
| **Red** | Conectividad a internet para `git pull` y `apt-get` |
| **Dependencias base** | `git`, `curl`, `systemctl` (preinstalados en DietPi) |
| **IP del nodo** | `192.168.1.141` (configurable) |

### Ejecución

```bash
# 1. Clonar el repositorio (si es primera instalación)
git clone https://github.com/<tu-usuario>/edge-sec-agent.git /root/edge-sec-agent
cd /root/edge-sec-agent

# 2. Hacer ejecutable el script de despliegue
chmod +x scripts/remote_deploy.sh

# 3. Ejecutar despliegue automático
bash scripts/remote_deploy.sh
```

### Flujo Interno Automatizado (7 Pasos)

El script `scripts/remote_deploy.sh` ejecuta de forma atómica las siguientes operaciones:

| Paso | Acción | Detalle |
|:----:|:-------|:--------|
| **1/7** | Git Pull | `git pull --rebase --autostash` en `/root/edge-sec-agent` |
| **2/7** | Instalar dependencias | `apt-get install nginx python3-pip python3-venv`. Crea entorno virtual `venv/` si no existe. Instala `flask` y `gunicorn` vía pip. |
| **3/7** | Configurar Nginx | Copia `nginx_agent.conf` a `/etc/nginx/sites-available/`, crea symlink en `/etc/nginx/sites-enabled/`. Elimina site default. Valida config con `nginx -t` y recarga. |
| **4/7** | Instalar servicio systemd | Mata procesos Flask/Gunicorn anteriores. Copia `edge-sec-agent.service` a `/etc/systemd/system/`. Ejecuta `daemon-reload`, `enable`, `restart`. |
| **5/7** | Verificar servicios | Comprueba que `edge-sec-agent.service` está activo. Health check a `127.0.0.1:5000` (Gunicorn) y `127.0.0.1:8080` (Nginx). |
| **6/7** | Hardening Dropbear | Modifica `/etc/default/dropbear` para forzar `DROPBEAR_PORT=2222`. Reinicia dropbear. Verifica con `ss -tlnp` que solo escucha en 2222. |
| **7/7** | Bloquear puerto 22 | Detecta puerto de sesión SSH actual via `$SSH_CONNECTION`. Si NO es puerto 22, aplica `iptables -I INPUT -p tcp --dport 22 -j DROP` para IPv4 e IPv6. Protección anti-lockout incluida. |

---

## Gestión del Servicio (Systemd)

El servicio `edge-sec-agent.service` gestiona el ciclo de vida de Gunicorn de forma persistente. Configurado con `Restart=always` y `RestartSec=5`, se recupera automáticamente ante fallos o reinicios del sistema.

### Comandos de Administración

```bash
# Ver estado del servicio
systemctl status edge-sec-agent.service

# Iniciar el servicio
systemctl start edge-sec-agent.service

# Detener el servicio
systemctl stop edge-sec-agent.service

# Reiniciar el servicio (aplica cambios de código)
systemctl restart edge-sec-agent.service

# Recargar configuración sin downtime (SIGHUP)
systemctl reload edge-sec-agent.service

# Habilitar arranque automático al boot
systemctl enable edge-sec-agent.service

# Deshabilitar arranque automático
systemctl disable edge-sec-agent.service
```

### Consulta de Logs

```bash
# Logs del servicio en tiempo real
journalctl -u edge-sec-agent.service -f

# Logs de las últimas 2 horas
journalctl -u edge-sec-agent.service --since "2 hours ago"

# Logs con prioridad de error o superior
journalctl -u edge-sec-agent.service -p err

# Logs de Gunicorn (acceso)
tail -f /var/log/gunicorn-edge-access.log

# Logs de Gunicorn (errores)
tail -f /var/log/gunicorn-edge-error.log

# Logs de Nginx (edge-sec-agent)
tail -f /var/log/nginx/edge-sec-agent-access.log
tail -f /var/log/nginx/edge-sec-agent-error.log
```

### Verificación Post-Despliegue

```bash
# Verificar que Gunicorn escucha en 127.0.0.1:5000
ss -tlnp | grep 5000

# Verificar que Nginx escucha en 0.0.0.0:8080
ss -tlnp | grep 8080

# Verificar que Dropbear escucha SOLO en 2222
ss -tlnp | grep -E '22|2222'

# Health check via Nginx
curl -s http://192.168.1.141:8080/v1/global/health | python3 -m json.tool

# Métricas Prometheus
curl -s http://192.168.1.141:8080/metrics

# Dashboard
curl -s http://192.168.1.141:8080/
```

---

## Estructura del Proyecto

```
edge-sec-agent/
├── src/
│   ├── agent.py              # Motor principal de análisis de seguridad
│   ├── sec_web.py            # Aplicación Flask (endpoints REST)
│   └── database.py           # Persistencia SQLite + retención automática
├── mcp_tools/                # Herramientas de diagnóstico ejecutables
│   ├── check_disk            # Uso de disco y espacio disponible
│   ├── check_cpu             # Carga de CPU y core count
│   ├── check_ram             # Uso de memoria RAM
│   ├── check_fail2ban        # Estado de jails e IPs bloqueadas
│   ├── check_connections     # Conexiones de red activas
│   ├── check_updates         # Actualizaciones de sistema pendientes
│   ├── check_processes       # Procesos en ejecución
│   ├── show_history          # Historial de métricas de seguridad
│   ├── log-analyzer          # Análisis de logs del sistema
│   └── ...                   # +10 herramientas adicionales
├── scripts/
│   ├── sec                   # CLI principal del agente
│   ├── sec-agent             # Wrapper de ejecución del agente
│   ├── sec-chat              # CLI para chat y herramientas MCP
│   └── remote_deploy.sh      # Script de despliegue automatizado (7 pasos)
├── edge-sec-agent.service    # Unit de systemd para Gunicorn
├── nginx_agent.conf          # Configuración de Nginx reverse proxy
├── wsgi.py                   # Entry point WSGI para producción
└── README.md                 # Documentación técnica (este archivo)
```

## Endpoints de la API

| Ruta | Método | Content-Type | Descripción |
|:-----|:-------|:-------------|:------------|
| `/` | GET | text/html | Dashboard principal con enlaces a métricas |
| `/api/metrics` | GET | application/json | Métricas de seguridad en formato JSON |
| `/v1/global/health` | GET | application/json | Health check estructurado del nodo |
| `/metrics` | GET | text/plain | Métricas en formato Prometheus (scrapeable) |

### Ejemplo de respuesta: `/v1/global/health`

```json
{
  "status": "HEALTHY",
  "device": "Orange Pi Zero 3",
  "environment": "production",
  "metrics_summary": "...",
  "hardware": {
    "cpu_temp_c": 42.5
  }
}
```

### Ejemplo de respuesta: `/metrics` (Prometheus)

```
# HELP edge_sec_cpu_temperature_celsius CPU temperature in Celsius
# TYPE edge_sec_cpu_temperature_celsius gauge
edge_sec_cpu_temperature_celsius 42.5
# HELP edge_sec_ram_used_percentage RAM usage percentage
# TYPE edge_sec_ram_used_percentage gauge
edge_sec_ram_used_percentage 67.3
```

---

**Plataforma**: Orange Pi Zero 3 | DietPi / Debian 12 | ARM64
**IP de producción**: 192.168.1.141
**Estado**: Producción activa
