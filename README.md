# 🛡️ Edge Security Agent (Orange Pi Zero 3)

[![Security Stack](https://img.shields.io/badge/Security-Hardened-red.svg)](#)
[![Platform](https://img.shields.io/badge/Hardware-Orange%20Pi%20Zero%203-orange.svg)](#)
[![OS](https://img.shields.io/badge/OS-DietPi%20%2F%20Debian%2012-blue.svg)](#)

Ecosistema de seguridad perimetral diseñado para entornos embebidos (Edge Computing). Implementa un proxy inverso endurecido, control de acceso estricto, mitigación de ataques de fuerza bruta en tiempo real (Capa 7) y optimización de escritura en almacenamiento Flash (SD).

---

## 🏗️ Arquitectura de Red y Capas de Seguridad Verificadas

El sistema mitiga de manera proactiva el ruido en red y protege el core de la API mediante un aislamiento estricto bajo proxy inverso:

| Componente / Servicio | Interfaz / IP | Puerto | Función / Control de Seguridad |
| :--- | :--- | :---: | :--- |
| **Cortafuegos Local** | `0.0.0.0` / `::/0` | **22** | ⛔ **DROP Total** (Persistente a nivel de kernel vía `iptables`) |
| **Consola SSH (Dropbear)**| `0.0.0.0` | **2222** | 🟢 Puerto alternativo protegido y supervisado por Fail2Ban |
| **Proxy Inverso (Nginx)** | `0.0.0.0` | **8443** | 🔒 HTTPS (TLS 1.2/1.3), Rate Limiting, Cabeceras HSTS, Basic Auth |
| **Backend Core (Gunicorn)**| `127.0.0.1` | **5000** | 🕵️ **Aislado** en Loopback (Inaccesible desde el exterior) |

---

## 📦 Optimizaciones para Hardware Edge

Para preservar el ciclo de vida de la tarjeta MicroSD (problema crítico en dispositivos perimetrales), el agente delega la auditoría a **DietPi-Ramlog**. 
- Fail2Ban procesa los buffers de registro directamente en **memoria volátil (RAM)**.
- Inspección activa sobre el log de errores dedicado: `/var/log/nginx/edge-sec-agent-error.log`.

---

## 🚀 Guía de Uso: Demostración Automatizada en Vivo (Live Demo)

Para las pruebas de evaluación ante el tribunal, se incluye un script en PowerShell 5.1 que automatiza la simulación de un ataque de fuerza bruta por Capa 7 HTTP:

```powershell
# 1. Navegar al directorio del agente
cd C:\Users\jaime\edge-sec-agent

# 2. Lanzar el disparador de la simulación
.\tests\live_demo_trigger.ps1
```

---

## 📊 Matriz de Hardening Aplicado

| Control | Implementación | Estado |
| :--- | :--- | :---: |
| SSH por defecto (22) | `iptables -I INPUT -p tcp --dport 22 -j DROP` | ✅ Activo |
| SSH alternativo | Dropbear en puerto 2222 | ✅ Activo |
| TLS/HTTPS | Certificado auto-firmado 2048-bit (365 días) | ✅ Activo |
| Rate Limiting | `limit_req_zone` 5r/s con burst=10 | ✅ Activo |
| Basic Auth | `auth_basic` protegido con `.htpasswd` | ✅ Activo |
| Security Headers | HSTS, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection | ✅ Activos |
| Fail2Ban (SSH) | Jaula `dropbear` en `/var/log/auth.log` | ✅ Activo |
| Fail2Ban (HTTP) | Jaula `nginx-http-auth` en `/var/log/nginx/error.log` | ✅ Activo |
| Retención de datos | `prune_old_metrics(days=30)` en SQLite | ✅ Activo |
| Persistencia de servicio | `systemd` con `Restart=always` | ✅ Activo |

---

## 🔧 Despliegue Rápido

```bash
# Clonar y desplegar en la Orange Pi
cd /root/edge-sec-agent
git pull
bash scripts/remote_deploy.sh
```

---

## 📁 Estructura del Repositorio

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
│   └── presentation_guide.md # Guía de defensa ante tribunal
├── edge-sec-agent.service    # Unit de systemd para Gunicorn
├── nginx_agent.conf          # Configuración de Nginx reverse proxy
├── wsgi.py                   # Entry point WSGI para producción
└── README.md                 # Documentación técnica (este archivo)
```

---

**Plataforma**: Orange Pi Zero 3 | DietPi / Debian 12 | ARM64
**IP de producción**: 192.168.1.141
**Estado**: Producción activa
