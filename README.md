[![CI](https://github.com/jqime/edge-sec-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/jqime/edge-sec-agent/actions/workflows/ci.yml)
![Tests](https://img.shields.io/badge/tests-38%20passed-brightgreen)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Platform](https://img.shields.io/badge/platform-ARM64-orange)

# Edge Security Agent: Arquitectura Hardened para Entornos Embebidos (Orange Pi Zero 3)

## 1. Resumen Ejecutivo

Este proyecto implementa un ecosistema perimetral autónomo de seguridad (DevSecOps) optimizado para dispositivos de computación en el borde (Edge Computing) bajo la plataforma de hardware Orange Pi Zero 3. La solución unifica mecanismos de mitigación en la capa de transporte y aplicación (Modelos OSI 4 y 7), protegiendo servicios locales mediante un proxy inverso endurecido, control de acceso basado en credenciales, tasa límite de peticiones (Rate Limiting) y bloqueo automatizado ante ataques de fuerza bruta en tiempo real, garantizando simultáneamente la preservación de los ciclos de vida de los medios de almacenamiento Flash (MicroSD).

## 2. Matriz de Arquitectura de Red y Segmentación de Servicios

La infraestructura del agente está diseñada bajo el principio de mínimos privilegios y reducción de superficie de ataque, aislando los servicios críticos en interfaces locales inactivas para el exterior:

| Componente / Servicio | Interfaz de Red | Puerto | Directiva de Seguridad y Control de Acceso |
| :--- | :--- | :---: | :--- |
| **Firewall Perimetral** | `0.0.0.0` / `::/0` | 22 | Directiva `DROP` total y persistente a nivel de Kernel mediante `iptables`. |
| **Servicio SSH (Dropbear)** | `0.0.0.0` | 2222 | Puerto alternativo de administración, supeditado a análisis de heurística por Fail2Ban. |
| **Proxy Inverso (Nginx)** | `0.0.0.0` | 8443 | Terminación TLS (1.2/1.3), inyección de cabeceras de seguridad y autenticación básica HTTP. |
| **Core de la API (Gunicorn)** | `127.0.0.1` | 5000 | Aislamiento estricto en interfaz de Loopback. Inaccesible a peticiones externas directas. |

## 3. Justificación Técnica de Decisiones de Diseño (Nivel Senior)

### 3.1. Mitigación de Degradación en Almacenamiento Sólido (Flash/SD)

Los dispositivos embebidos basados en tarjetas MicroSD sufren de corrupción prematura de datos debido a la alta frecuencia de operaciones de escritura (*Write Amplification*). Para mitigar este vector de fallo físico:

* **DietPi-Ramlog Interception:** El sistema desvía los buffers de registro hacia memoria volátil (RAM).
* **Análisis Focalizado:** Se configuró la jaula de Fail2Ban (`nginx-http-auth`) para auditar exclusivamente el descriptor de archivo `/var/log/nginx/edge-sec-agent-error.log`, optimizando el consumo de CPU y evitando escrituras síncronas en disco por cada intento de intrusión.

### 3.2. Endurecimiento de la Capa de Transporte (Capa 7 HTTP/TLS)

El archivo `nginx_agent.conf` implementa un perfil estricto de criptografía asimétrica:

* **Restricción de Cifrado:** Se deshabilitan protocolos inseguros (TLS 1.0 y 1.1), forzando el uso exclusivo de TLS 1.2 y TLS 1.3 con suites de cifrado basadas en curvas elípticas con secreto perfecto hacia adelante (*Perfect Forward Secrecy*).
* **Cabeceras de Hardening:** Inyección sistemática de cabeceras HTTP (`Strict-Transport-Security`, `X-Frame-Options DENY`, `X-Content-Type-Options nosniff`) para anular vectores de ataque como Cross-Site Scripting (XSS) y Clickjacking.

## 4. Matriz de Controles de Seguridad Implementados

| Control Implementado | Mecanismo de Verificación | Estado Operativo |
| :--- | :--- | :---: |
| Oclusión de Puerto Estándar (22) | `iptables -L INPUT -n -v` (Verificación de política DROP) | Confirmado |
| Ofuscación de SSH de Gestión | Escucha activa Dropbear en puerto `2222` | Confirmado |
| Robustez Criptográfica | Verificación TLS mediante negociación local OpenSSL | Confirmado |
| Control de Flujo (Rate Limiting) | Directiva `limit_req_zone` limitada a 5r/s con ráfaga (*burst*) de 10 | Confirmado |
| Control de Acceso Capa 7 | Validación de vectores criptográficos en `/etc/nginx/.htpasswd` | Confirmado |
| Monitorización de Fuerza Bruta | Jaula Fail2Ban analizando firmas de error 401 en Nginx | Confirmado |
| Integridad de Base de Datos | Rutina automatizada de depuración SQLite `prune_old_metrics(days=30)` | Confirmado |
| Resiliencia de Procesos | Orquestación mediante unidades de servicio de Systemd (`Restart=always`) | Confirmado |

## 5. Guías Operacionales e Instrucciones de Uso

### 5.1. Ejecución de Simulación de Ataque Automatizado (Live Demo)

Para validar de forma empírica la convergencia entre Nginx (Detección de accesos no autorizados) y el Firewall (Bloqueo de red), se ha dispuesto un script de pruebas determinista en `tests/live_demo_trigger.ps1` ejecutable en consolas Windows PowerShell 5.1+:

```powershell
# Acceder a la raíz del espacio de trabajo
cd C:\Users\jaime\edge-sec-agent

# Lanzar el script de auditoría perimetral dinámica
.\tests\live_demo_trigger.ps1
```

El script realiza un login exitoso inicial (HTTP 200) seguido de ráfagas controladas de logins erróneos. Al alcanzar el umbral crítico configurado en el archivo jail.local (maxretry = 3), el script capturará un error inmediato de denegación de conexión física, confirmando el baneo en caliente de la IP emisora.

### 5.2. Comandos de Administración del Sistema de Seguridad (Orange Pi SSH)

Para gestionar las contingencias o monitorizar la actividad del agente desde la terminal Linux de la placa (Puerto 2222), utilice las siguientes herramientas de consola:

Inspección del Estado de la Jaula HTTP:

```bash
fail2ban-client status nginx-http-auth
```

Remoción Manual de Bloqueo (Unban IP):

```bash
fail2ban-client set nginx-http-auth unbanip <IP_OBJETIVO>
```

Trazabilidad de Logs de Error en Tiempo Real:

```bash
tail -f /var/log/nginx/edge-sec-agent-error.log
```

### 5.3. Kit de Herramientas de Diagnóstico MCP (Model Context Protocol)

El repositorio incorpora un conjunto de scripts ejecutables dentro del directorio `mcp_tools/` diseñados para auditorías sanitarias del sistema de manera automatizada:

* `./mcp_tools/check_fail2ban`: Retorna métricas analíticas sobre el volumen de IPs bloqueadas.
* `./mcp_tools/check_connections`: Mapea los sockets de red abiertos en interfaces de escucha.
* `./mcp_tools/show_history`: Extrae resúmenes estadísticos de la base de datos analítica SQLite.

### 5.4. Estructura del Repositorio

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
│   └── log-analyzer          # Análisis de logs del sistema
├── scripts/
│   ├── sec                   # CLI principal del agente
│   ├── sec-agent             # Wrapper de ejecución del agente
│   ├── sec-chat              # CLI para chat y herramientas MCP
│   ├── remote_deploy.sh      # Script de despliegue automatizado (7 pasos)
│   └── security_audit.sh     # Auditoría automatizada de 5 controles perimetrales
├── tests/
│   └── live_demo_trigger.ps1 # Simulación de ataque fuerza bruta (PowerShell 5.1)
├── docs/
│   ├── presentation_guide.md # Guía de defensa ante tribunal
│   ├── api_spec.yaml         # Contrato OpenAPI 3.0.3 de los endpoints REST
│   └── architecture.txt      # Diagrama de flujo arquitectónico
├── .github/workflows/
│   └── ci.yml                # Pipeline CI/CD (GitHub Actions)
├── edge-sec-agent.service    # Unit de systemd para Gunicorn
├── nginx_agent.conf          # Configuración de Nginx reverse proxy
├── wsgi.py                   # Entry point WSGI para producción
├── Dockerfile                # Definición de contenedor alternativo
├── Makefile                  # Orquestador de comandos locales
├── requirements.txt          # Dependencias Python formales
├── secrets.env.example       # Plantilla de variables de entorno
├── LICENSE                   # Licencia MIT
├── CHANGELOG.md              # Historial de versiones
└── README.md                 # Documentación técnica (este archivo)
```

---

**Especificaciones de Entorno:** Hardware: Orange Pi Zero 3 (ARM64) | Sistema Operativo: DietPi v12 (Debian Bookworm) | Estado del Entorno: Producción Verificada.
