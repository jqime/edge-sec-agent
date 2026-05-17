# Edge Sec Agent

Plataforma DevSecOps de monitorización y seguridad perimetral para dispositivos embebidos (Orange Pi Zero 3). Proporciona análisis de seguridad en tiempo real, herramientas MCP extensibles, dashboard web con métricas Prometheus y endurecimiento automático del sistema.

## Arquitectura

```
Internet/Red Local
        |
        v
┌─────────────────────────────────────────┐
│  Nginx Reverse Proxy (0.0.0.0:8080)     │
│  - client_max_body_size: 10M            │
│  - Rutas: /, /health, /metrics, /api/*  │
└──────────────────┬──────────────────────┘
                   | proxy_pass
                   v
┌─────────────────────────────────────────┐
│  Gunicorn WSGI (127.0.0.1:5000)         │
│  - Workers: 2                           │
│  - Timeout: 120s                        │
│  - Flask App (src/sec_web.py)           │
└────┬──────────────┬──────────────┬──────┘
     |              |              |
     v              v              v
┌────────┐   ┌──────────┐   ┌────────────┐
│ SQLite │   │ MCP      │   │ System     │
│ Metrics│   │ Tools    │   │ Commands   │
│ (DB)   │   │ (bash)   │   │ (ss, ipt.) │
└────────┘   └──────────┘   └────────────┘
```

### Flujo de peticiones
1. **Nginx** recibe tráfico en `:8080` y lo proxy-a a Gunicorn en `127.0.0.1:5000`
2. **Gunicorn** ejecuta la app Flask (`wsgi:app`) con 2 workers
3. **Flask** expone endpoints de métricas, salud y dashboard
4. **SQLite** persiste métricas históricas con retención automática de 30 días
5. **MCP Tools** ejecutan diagnósticos del sistema (disk, cpu, ram, fail2ban, etc.)

## Matriz de Puertos

| Puerto | Protocolo | Servicio | Acceso | Notas |
|--------|-----------|----------|--------|-------|
| **2222** | TCP | Dropbear SSH | Restringido | Único puerto SSH autorizado. Puerto 22 bloqueado por iptables |
| **8080** | TCP | Nginx Proxy | Público | Dashboard, API REST, métricas Prometheus |
| **5000** | TCP | Gunicorn | Solo localhost | No expuesto directamente. Accesible via Nginx |

### Endpoints disponibles (via `:8080`)

| Ruta | Método | Descripción |
|------|--------|-------------|
| `/` | GET | Dashboard principal |
| `/api/metrics` | GET | Métricas de seguridad en JSON |
| `/v1/global/health` | GET | Health check estructurado |
| `/metrics` | GET | Formato Prometheus (text/plain) |

## Estructura del Proyecto

```
edge-sec-agent/
├── src/
│   ├── agent.py           # Motor principal de análisis de seguridad
│   ├── sec_web.py         # Aplicación Flask (endpoints web)
│   └── database.py        # Persistencia SQLite + retención de datos
├── mcp_tools/             # Herramientas de diagnóstico ejecutables
│   ├── check_disk         # Uso de disco
│   ├── check_cpu          # Carga de CPU
│   ├── check_ram          # Uso de memoria
│   ├── check_fail2ban     # Estado de jails e IPs bloqueadas
│   ├── check_connections  # Conexiones activas
│   ├── check_updates      # Actualizaciones pendientes
│   ├── check_processes    # Procesos en ejecución
│   ├── show_history       # Historial de métricas
│   ├── log-analyzer       # Análisis de logs
│   └── ...                # +10 herramientas adicionales
├── scripts/
│   ├── sec                # CLI principal
│   ├── sec-agent          # Wrapper de agente
│   ├── sec-chat           # CLI para chat y herramientas MCP
│   └── remote_deploy.sh   # Script de despliegue en producción
├── edge-sec-agent.service # Unit de systemd para Gunicorn
├── nginx_agent.conf       # Configuración de Nginx
├── wsgi.py                # Entry point WSGI
└── README.md              # Este archivo
```

## Despliegue en un solo paso

### Prerrequisitos
- Orange Pi Zero 3 con Debian 12 / DietPi
- Acceso root via SSH
- Git instalado
- Conexión a internet

### Comando de despliegue

```bash
# Clonar y desplegar automáticamente
git clone https://github.com/<tu-usuario>/edge-sec-agent.git /root/edge-sec-agent
cd /root/edge-sec-agent
chmod +x scripts/remote_deploy.sh
bash scripts/remote_deploy.sh
```

El script `remote_deploy.sh` ejecuta automáticamente 7 pasos:
1. **Git pull** - Actualiza código desde el repositorio
2. **Instalar dependencias** - Nginx, Python venv, Flask, Gunicorn
3. **Configurar Nginx** - Proxy inverso en puerto 8080
4. **Instalar servicio systemd** - Gunicorn persistente con `Restart=always`
5. **Verificar servicios** - Health checks de Gunicorn y Nginx
6. **Hardening Dropbear** - Fuerza SSH en puerto 2222, deshabilita puerto 22
7. **Bloquear puerto 22** - Reglas iptables IPv4 + IPv6

### Gestión del servicio

```bash
# Estado del servicio
systemctl status edge-sec-agent

# Reiniciar
systemctl restart edge-sec-agent

# Ver logs
journalctl -u edge-sec-agent -f

# Logs de Gunicorn
tail -f /var/log/gunicorn-edge-error.log
tail -f /var/log/gunicorn-edge-access.log

# Logs de Nginx
tail -f /var/log/nginx/edge-sec-agent-error.log
```

## MCP Tools

Las herramientas MCP se ejecutan via `sec-chat --tool <nombre>`:

```bash
# Ejemplos de uso
sec-chat --tool check_disk
sec-chat --tool check_cpu
sec-chat --tool check_fail2ban
sec-chat --tool show_history

# Planes de seguridad predefinidos
sec-chat --plan "fallos ssh"
sec-chat --plan "firewall"
sec-chat --plan "puertos"
```

## Base de Datos SQLite

- **Ubicación**: `/root/edge-sec-agent/data/edge_metrics.db`
- **Tabla**: `metrics` (id, timestamp, cpu_usage, ram_usage, cpu_temp, banned_ips)
- **Retención automática**: Registros mayores a 30 días se eliminan en cada inicialización
- **Función manual**: `prune_old_metrics(days=30)` en `src/database.py`

## Seguridad

- **Secrets**: Almacenados en `/root/edge-sec-agent/secrets.env` (excluido de Git)
- **SSH**: Único puerto 2222, puerto 22 bloqueado por iptables
- **Gunicorn**: Escucha solo en `127.0.0.1` (no expuesto a red externa)
- **Nginx**: `client_max_body_size 10M` para prevenir abusos
- **Anti-lockout**: El script de despliegue detecta si tu sesión SSH usa puerto 22 y omite el bloqueo para evitar pérdida de acceso

## Licencia

MIT
