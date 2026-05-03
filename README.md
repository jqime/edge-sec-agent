# 🦞 Edge Sec Agent

Agente DevSecOps autónomo para Orange Pi Zero 3 – comandos rápidos, planificador por reglas, MCP y monitorización real

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://www.python.org/)
[![Ollama](https://img.shields.io/badge/Ollama-Local-brightgreen?logo=ollama)](https://ollama.com/)
[![Orange Pi](https://img.shields.io/badge/Orange%20Pi-Zero%203-orange)](http://www.orangepi.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)]()

## 🎯 ¿Qué hace?

**Edge Sec Agent** es un asistente de seguridad que corre **100% local** en tu Orange Pi Zero 3. No depende de la nube, ni de API Keys.

- 🔍 **Escaneo instantáneo** de red, puertos, procesos y temperatura.
- 🛡️ **Planificador por reglas** para tareas comunes (firewall, logs, fail2ban, actualizaciones).
- 🧠 **IA opcional** con Ollama y TinyLlama (1.1b) para preguntas complejas.
- 🛠️ **Herramientas MCP** extensibles (hardening, auditoría, scripts personalizados).
- 📊 **Monitorización automática** con alertas por cron.

## 🚀 Instalación en 30 segundos

```bash
git clone https://github.com/jqime/edge-sec-agent.git
cd edge-sec-agent
cp scripts/sec /usr/local/bin/
cp scripts/sec-chat /usr/local/bin/
chmod +x /usr/local/bin/sec /usr/local/bin/sec-chat
🔧 Comandos disponibles
sec – información del sistema en <1s
Comando	Descripción
sec status	IP, RAM, temperatura, fallos SSH
sec red	Dispositivos en la red local (ARP)
sec puertos	Puertos en escucha (ss -tlnp)
sec procesos	Procesos con mayor uso de CPU
sec temp	Temperatura del procesador
sec ram	Uso de memoria RAM
sec-chat – planificador y herramientas MCP
Modo	Ejemplo	Acción
--plan	sec-chat --plan "estado del firewall"	Ejecuta tareas comunes
--tool	sec-chat --tool harden	Ejecuta script MCP
(ninguno)	sec-chat "pregunta"	IA conversacional (lento)
🛠️ Herramientas MCP incluidas
harden – hardening básico (IPv6, MaxAuthTries, puertos abiertos)

audit – auditoría de seguridad (fallos SSH, sudo, servicios expuestos)

saludo – ejemplo para crear tus propias herramientas

🐳 Contenedor opcional: OpenWebUI
bash
docker run -d --name openwebui -p 3000:8080 --restart unless-stopped ghcr.io/open-webui/open-webui:main
Accede en http://tu-ip:3000

📊 Monitorización automática
Cron cada 30 minutos para fallos SSH y cada 5 minutos para temperatura (>70°C alerta). Logs en /var/log/syslog.

⚡ Rendimiento en Orange Pi Zero 3
Operación	Tiempo
sec status	< 1 segundo
sec-chat --plan	< 2 segundos
IA conversacional	~60-90 segundos
🔒 Seguridad
Todo local, sin nube.

Comandos peligrosos bloqueados.

MCP con permisos de usuario.

🗺️ Roadmap
Comandos rápidos (sec)

Planificador por reglas

Herramientas MCP

Monitorización por cron

OpenWebUI opcional

API REST local

Modo demonio avanzado

Soporte multi-modelo

📄 Licencia
MIT © Jaime Muñoz

Hecho con ❤️ para la comunidad DevSecOps en el borde – sin cloud, sin GPU, sin excusas.
