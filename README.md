# 🦞 Edge Sec Agent

**Agente SecDevOps autónomo corriendo en el borde — Orange Pi Zero 3**

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![Ollama](https://img.shields.io/badge/Ollama-TinyLlama%201.1b-orange)](https://ollama.com)
[![Platform](https://img.shields.io/badge/Platform-Orange%20Pi%20Zero%203%20(aarch64)-red)](https://orangepi.org)
[![OS](https://img.shields.io/badge/OS-DietPi%2010%20(Debian%2013)-green)](https://dietpi.com)

---

## 🎯 ¿Qué hace?

Edge Sec Agent es un agente de IA que corre **completamente en local** (sin cloud, sin API keys) sobre una Orange Pi Zero 3. Analiza el sistema en tiempo real usando datos reales del SO y responde preguntas de SecDevOps en español.

```
💬 > ¿Hay algún puerto sospechoso abierto?
🤖 El sistema tiene abiertos los puertos 22 (SSH), 11434 (Ollama) y 8080 (WebUI).
   El puerto 22 tiene 3 intentos de login fallidos registrados.
   Recomendación: revisar /etc/fail2ban/jail.conf y restringir acceso SSH por IP.
⏱️  38.2s
```

---

## 🏗️ Arquitectura real

```
┌─────────────────────────────────────────────┐
│           Orange Pi Zero 3                  │
│  ┌──────────────┐   ┌─────────────────────┐ │
│  │  agent.py    │──▶│  Ollama :11434       │ │
│  │  (Python)    │   │  TinyLlama 1.1b      │ │
│  └──────┬───────┘   │  637 MB GGUF Q4_0   │ │
│         │           └─────────────────────┘ │
│         │ ss / free / hostname / lastb       │
│         ▼                                   │
│  [datos reales del SO]                      │
└─────────────────────────────────────────────┘
         │ SSH / VS Code Remote
         ▼
  PC Windows (desarrollo)
```

| Componente | Detalle |
|---|---|
| Hardware | Orange Pi Zero 3 — 4 núcleos Cortex-A53 @ 1.5 GHz, 4 GB RAM |
| SO | DietPi 10.3.3 (Debian 13 Bookworm, aarch64) |
| IA runtime | Ollama — sin GPU, solo CPU |
| Modelo | TinyLlama 1.1b (Q4_0, 637 MB) |
| Lenguaje | Python 3.11 — solo stdlib, sin dependencias externas |
| Red | LAN: `192.168.1.141` (eth0) |

---

## 🚀 Inicio rápido

### Prerequisitos

```bash
# En la Orange Pi (DietPi)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull tinyllama:1.1b
```

### Instalación

```bash
git clone https://github.com/jqime/edge-sec-agent.git
cd edge-sec-agent
```

### Uso

```bash
# Modo interactivo
python3 src/agent.py

# Análisis de seguridad automático
python3 src/agent.py --security

# Estado del sistema (sin IA)
python3 src/agent.py --status

# Pregunta directa
python3 src/agent.py "¿Cuánta RAM libre hay?"
```

---

## 📁 Estructura del proyecto

```
edge-sec-agent/
├── src/
│   └── agent.py          # Agente principal
├── scripts/
│   ├── start.sh          # Inicio limpio del agente
│   └── health_check.sh   # Verificación del sistema
├── docs/
│   ├── SETUP.md          # Guía de instalación completa
│   └── ARCHITECTURE.md   # Decisiones de diseño
├── .gitignore
└── README.md
```

---

## ⚙️ Configuración

El agente se configura mediante variables de entorno:

| Variable | Default | Descripción |
|---|---|---|
| `EDGE_MODEL` | `tinyllama:1.1b` | Modelo Ollama a usar |
| `EDGE_MAX_TOKENS` | `120` | Máximo de tokens por respuesta |
| `EDGE_TIMEOUT` | `180` | Timeout en segundos |
| `EDGE_TEMP` | `0.3` | Temperatura del modelo (0=determinista) |

Ejemplo:

```bash
EDGE_MODEL=qwen2:0.5b EDGE_MAX_TOKENS=80 python3 src/agent.py "hola"
```

---

## ⚡ Rendimiento en Orange Pi Zero 3

| Operación | Tiempo |
|---|---|
| Primera carga del modelo | ~18–30 s |
| Generación (20 tokens) | ~5 s |
| Generación (120 tokens) | ~30–60 s |
| Temperatura CPU en carga | 45–55 °C |

> **Tip:** Reinicia Ollama si el agente se bloquea. Los `Ctrl+C` dejan peticiones
> pendientes en el servidor: `systemctl restart ollama && sleep 20`

---

## 🔒 Seguridad

- Todo corre en local — ningún dato sale de la red
- El modelo no tiene acceso a Internet
- El agente solo lee datos del SO (no escribe ni ejecuta como root)
- Acceso SSH protegido con fail2ban

---

## 🗺️ Roadmap

- [x] v0.1 — Agente básico con Ollama
- [x] v0.2 — Streaming de tokens en tiempo real  
- [x] v0.3 — Contexto real del sistema (puertos, RAM, fallos login)
- [ ] v0.4 — Modo demonio con alertas periódicas
- [ ] v0.5 — API REST local para integración con otros servicios
- [ ] v0.6 — Soporte multi-modelo (qwen2:0.5b / phi3:mini)

---

## 👤 Autor

**Jaime Muñoz** — SecDevOps @ CDS Race Experience  
Proyecto: IA en el borde, sin cloud, sin GPU, sin excusas.