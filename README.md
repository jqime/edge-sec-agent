# 🦞 Edge Sec Agent

<p align="center">
  <img src="https://img.icons8.com/color/96/000000/security-checked--v1.png" width="80"/>
  <br />
  <i>Agente DevSecOps autónomo para Orange Pi Zero 3 – comandos rápidos, planificador por reglas, IA local y alertas en tiempo real</i>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white" alt="Python 3.11" /></a>
  <a href="https://ollama.com/"><img src="https://img.shields.io/badge/Ollama-Local-brightgreen?logo=ollama" alt="Ollama Local" /></a>
  <a href="http://www.orangepi.org/"><img src="https://img.shields.io/badge/Orange%20Pi-Zero%203-orange" alt="Orange Pi Zero 3" /></a>
  <a href="#"><img src="https://img.shields.io/badge/License-MIT-green" alt="MIT License" /></a>
  <a href="#"><img src="https://img.shields.io/badge/Status-Production%20Ready-brightgreen" alt="Production Ready" /></a>
  <a href="https://github.com/jqime/edge-sec-agent"><img src="https://img.shields.io/github/stars/jqime/edge-sec-agent?style=social" alt="GitHub stars" /></a>
</p>

---

## 🎯 ¿Qué hace?

**Edge Sec Agent** es un asistente de seguridad que corre **100% local** en tu Orange Pi Zero 3. No depende de la nube, ni de API Keys. Combina:

- 🔍 **Comandos instantáneos** (`sec`) para obtener información del sistema en <1s.
- 🛡️ **Planificador por reglas** (`sec-chat --plan`) para tareas comunes (firewall, logs, fail2ban, actualizaciones).
- 🧠 **IA conversacional** (`ia` o `sec-agent`) con modelos locales (`qwen2.5:0.5b`, `tinyllama`, etc.)
- 🛠️ **Herramientas MCP** extensibles (hardening, auditoría, scripts personalizados).
- 📊 **Monitorización automática** con alertas por Telegram y cron.
- 🔌 **API REST** para integraciones con otros servicios.
- 🐳 **OpenWebUI** (opcional) como interfaz web para interactuar con la IA.

---

## 🚀 Instalación en 30 segundos

```bash
git clone https://github.com/jqime/edge-sec-agent.git
cd edge-sec-agent
cp scripts/sec scripts/sec-chat scripts/sec-agent scripts/ia /usr/local/bin/
chmod +x /usr/local/bin/sec /usr/local/bin/sec-chat /usr/local/bin/sec-agent /usr/local/bin/ia
Requisitos previos:

bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:0.5b
🔧 Comandos disponibles
⚡ sec – información del sistema en <1s
Comando	Descripción
sec status	IP, RAM, temperatura, puertos abiertos, fallos SSH
sec red	Dispositivos en la red local (ARP)
sec puertos	Puertos en escucha
sec procesos	Procesos con mayor uso de CPU
sec temp	Temperatura del procesador
sec ram	Uso de memoria RAM


🧠 sec-agent – selector automático
Detecta si la consulta es operativa (reglas rápidas) o conversacional (IA).

bash
sec-agent "estado del sistema"            # reglas: <2s
sec-agent "¿cómo mejorar la seguridad?"   # IA: 10-90s
🤖 ia – IA conversacional directa
bash
ia "¿qué puertos están abiertos?"
ia "dame consejos de seguridad para SSH"
🛠️ sec-chat – planificador por reglas y herramientas MCP
Modo reglas (--plan)
Regla	Acción
fallos ssh	Muestra intentos fallidos
estado del firewall	Reglas UFW
actualizar paquetes	Lista actualizaciones
fail2ban status	Estado de fail2ban
reiniciar docker	Reinicia Docker
escanear puertos localhost	Nmap
bloquear ip X	iptables


Ejemplo:

bash
sec-chat --plan "estado del firewall"
Herramientas MCP (--tool)
Herramienta	Función
harden	Hardening básico
audit	Auditoría de seguridad
security-score	Puntuación 0–100
forensic-snapshot	Instantánea forense
event-correlator	Correlación de eventos
ir-response	Respuesta a incidentes
custom-report	Informes diarios/semanales
backup	Respaldo de configuraciones
vuln-scan	Escaneo Lynis
saludo	Ejemplo para crear tus propias herramientas


Ejemplo:

bash
sec-chat --tool security-score
Crear herramientas personalizadas:

bash
~/mcp_tools/mi_script
sec-chat --tool mi_script
🔌 API REST
Servicio activo en el puerto 8765.

Endpoint
Código
POST /ask
Ejemplo
bash
curl -X POST http://localhost:8765/ask \
  -H "Content-Type: application/json" \
  -d '{"pregunta": "status"}'
Respuesta:

json
{"respuesta": "IP 192.168.1.141 | RAM 1.9Gi/3.8Gi | Temp 34.1C | Puertos 22 3000 8765 ... | Fallos SSH 2"}
🐳 OpenWebUI (opcional)
bash
docker run -d --name openwebui \
  --add-host host.docker.internal:host-gateway \
  -p 3000:8080 --restart unless-stopped \
  ghcr.io/open-webui/open-webui:main
Accede en:

Código
http://TU_IP:3000
📊 Monitorización automática (cron)
El agente instala tareas que:

Cada 10 min → alerta si hay >5 fallos SSH

Cada 5 min → alerta si la temperatura >60 °C

Cada 1 hora → envía estado completo del sistema

Logs:

bash
grep "sec" /var/log/syslog
⚡ Rendimiento real en Orange Pi Zero 3
Operación	Tiempo
sec status	<1s
sec-chat --plan	<2s
sec-agent (operativo)	<2s
Herramienta MCP	<2s
ia qwen2.5:0.5b	10–20s
ia qwen2.5:3b	60–90s


🔒 Seguridad
Todo funciona offline, sin nube ni telemetría.

Comandos peligrosos bloqueados (rm, dd, mkfs, etc.).

MCP se ejecuta sin privilegios elevados.

API REST sin ejecución arbitraria.

IA aislada del shell.

Recomendado: fail2ban + cambio de puerto SSH.

🗺️ Roadmap
Comandos rápidos (sec)

Reglas (sec-chat --plan)

Herramientas MCP

Monitorización por cron

OpenWebUI

API REST

Selector automático (sec-agent)

IA conversacional (ia)

Modo demonio (sec-daemon)

Multi‑modelo (EDGE_MODEL)

📄 Licencia
MIT © Jaime Muñoz

<p align="center">
<sub>Hecho con ❤️ para la comunidad DevSecOps en el borde – sin cloud, sin GPU, sin excusas.</sub>
</p>