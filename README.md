# 🦞 Edge Sec Agent

Agente SecDevOps autónomo para Orange Pi Zero 3 – comandos rápidos, planificador por reglas, herramientas MCP y monitorización.

## 🚀 Instalación rápida

```bash
git clone https://github.com/jqime/edge-sec-agent.git
cd edge-sec-agent
cp scripts/sec /usr/local/bin/
cp scripts/sec-chat /usr/local/bin/
chmod +x /usr/local/bin/sec /usr/local/bin/sec-chat
🔧 Comandos disponibles
sec – información instantánea del sistema
Comando	Qué hace
sec status	IP, RAM, temperatura, fallos SSH
sec red	Dispositivos en la red local
sec puertos	Puertos en escucha
sec procesos	Procesos con mayor uso de CPU
sec temp	Temperatura de la CPU
sec ram	Uso de memoria RAM
sec-chat – planificador y herramientas MCP
Comando	Ejemplo	Acción
sec-chat --plan "..."	sec-chat --plan "estado del firewall"	Ejecuta tareas comunes (firewall, logs, fail2ban, actualizaciones)
sec-chat --tool nombre	sec-chat --tool harden	Ejecuta scripts personalizados en ~/mcp_tools/
🛠️ Herramientas MCP incluidas
harden – hardening básico (IPv6, MaxAuthTries, puertos abiertos)

audit – auditoría de seguridad (fallos SSH, usuarios sudo, servicios expuestos, paquetes desactualizados)

Puedes añadir tus propios scripts en ~/mcp_tools/ y ejecutarlos con sec-chat --tool nombre.

🐳 Contenedor opcional: OpenWebUI
Si tienes Docker, despliega una interfaz web para tus modelos de Ollama:

bash
docker run -d --name openwebui -p 3000:8080 --restart unless-stopped ghcr.io/open-webui/open-webui:main
Accede en http://tu-ip:3000

📊 Monitorización automática
El agente incluye un cron que cada 30 minutos comprueba nuevos fallos SSH y cada 5 minutos la temperatura (alerta si supera 70°C). Los logs se guardan en /var/log/syslog.

⚡ Rendimiento en Orange Pi Zero 3
Comandos sec: < 1 segundo

Planificador sec-chat --plan: < 2 segundos

Herramientas MCP: instantáneo

La IA conversacional (opcional) está basada en tinyllama:1.1b y puede tardar 60-90 segundos. Para el día a día, usa los comandos rápidos.

📁 Estructura del proyecto
text
edge-sec-agent/
├── scripts/
│   ├── sec           # Comandos rápidos
│   └── sec-chat      # Planificador y MCP
├── mcp_tools/        # Scripts personalizados
├── src/              # Código fuente original (agent.py)
└── docs/             # Documentación adicional
👤 Autor
Jaime Muñoz – SecDevOps @ CDS Race Experience
Proyecto: IA en el borde, sin cloud, sin GPU, sin excusas.
