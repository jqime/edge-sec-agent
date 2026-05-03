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
- 🧠 **IA conversacional** (`ia` o `sec-agent`) con modelos locales (qwen2.5:0.5b, tinyllama, etc.)
- 🛠️ **Herramientas MCP** extensibles (hardening, auditoría, scripts personalizados).
- 📊 **Monitorización automática** con alertas por Telegram y cron.

---

## 🚀 Instalación en 30 segundos

```bash
git clone https://github.com/jqime/edge-sec-agent.git
cd edge-sec-agent
cp scripts/sec scripts/sec-chat scripts/sec-agent scripts/ia /usr/local/bin/
chmod +x /usr/local/bin/sec /usr/local/bin/sec-chat /usr/local/bin/sec-agent /usr/local/bin/ia
🔧 Comandos disponibles
⚡ sec – información del sistema en <1s
Comando	Descripción
sec status	IP, RAM, temperatura, fallos SSH
sec red	Dispositivos en la red local (ARP)
sec puertos	Puertos en escucha (ss -tlnp)
sec procesos	Procesos con mayor uso de CPU
sec temp	Temperatura del procesador
sec ram	Uso de memoria RAM
🧠 sec-agent – selector automático (recomendado)
Detecta si la consulta es operativa (usa reglas rápidas) o conversacional (usa IA).

bash
sec-agent "estado del sistema"        # reglas: <2s
sec-agent "¿cómo mejorar la seguridad?" # IA: 10-90s
🤖 ia – IA conversacional directa
bash
ia "¿qué puertos están abiertos?"
ia "dame consejos de seguridad para SSH"
🛠️ sec-chat – planificador y herramientas MCP
Modo	Ejemplo	Acción
--plan	sec-chat --plan "estado del firewall"	Ejecuta tareas comunes (instantáneo)
--tool	sec-chat --tool harden	Ejecuta script MCP
(ninguno)	sec-chat "pregunta"	IA conversacional (lento, 60-90s)
🛠️ Herramientas MCP incluidas
Script	Función
harden	Hardening básico (IPv6, MaxAuthTries, puertos abiertos)
audit	Auditoría de seguridad (fallos SSH, sudo, servicios expuestos)
saludo	Ejemplo para crear tus propias herramientas
Crear tu propia herramienta MCP es tan simple como:

bash
echo -e '#!/bin/bash\necho "Hola $1"' > ~/mcp_tools/mi_script
chmod +x ~/mcp_tools/mi_script
sec-chat --tool mi_script "mundo"
🐳 Contenedor opcional: OpenWebUI
Despliega una interfaz web para chatear con tus modelos de Ollama:

bash
docker run -d --name openwebui --add-host host.docker.internal:host-gateway -p 3000:8080 --restart unless-stopped ghcr.io/open-webui/open-webui:main
Accede en http://tu-ip:3000

📊 Monitorización automática
El agente instala un cron que:

Cada 10 minutos comprueba fallos SSH >5 y envía alerta a Telegram.

Cada 5 minutos verifica la temperatura; si supera 60°C, lanza alerta.

Cada hora envía el estado completo del sistema.

Puedes revisar las alertas con:

bash
grep "sec" /var/log/syslog
⚡ Rendimiento real en Orange Pi Zero 3
Operación	Tiempo
sec status	< 1 segundo
sec-chat --plan	< 2 segundos
sec-agent (operativo)	< 2 segundos
Herramienta MCP	< 2 segundos
ia (modelo rápido qwen2.5:0.5b)	10‑20 segundos
ia (modelo calidad qwen2.5:3b)	60‑90 segundos
La IA es lenta por el hardware (4 núcleos ARM, sin GPU). Para el día a día, usa los comandos rápidos – son más que suficientes para tareas de administración y seguridad.

🔒 Seguridad
Todo el código y los modelos se ejecutan localmente (sin envío de datos a la nube).

Los comandos peligrosos (rm, dd, etc.) están bloqueados en el planificador.

Las herramientas MCP se ejecutan con los permisos del usuario, no como root.

El acceso SSH está protegido por fail2ban (recomendado).

🗺️ Roadmap
Comandos rápidos (sec)

Planificador por reglas (sec-chat --plan)

Herramientas MCP (sec-chat --tool)

Monitorización por cron

OpenWebUI como interfaz web opcional

API REST (sec-agent --api)

Selector automático (sec-agent)

IA conversacional directa (ia)

Modo demonio con alertas personalizables

Soporte multi‑modelo configurable

📄 Licencia
MIT © Jaime Muñoz

<p align="center"> <sub>Hecho con ❤️ para la comunidad DevSecOps en el borde – sin cloud, sin GPU, sin excusas.</sub> </p> ```
