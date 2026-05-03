# Guía de instalación completa

## Hardware necesario

- Orange Pi Zero 3 (1.5 GB RAM mínimo, recomendado 4 GB)
- MicroSD ≥ 16 GB (clase 10 o superior)
- Conexión ethernet o WiFi

## 1. Sistema operativo

Se usa **DietPi** (Debian 13, aarch64) por su bajo consumo de RAM comparado con Ubuntu.

Descarga la imagen desde [dietpi.com](https://dietpi.com/#download) y flashea con Balena Etcher.

## 2. Instalar Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
systemctl enable ollama
systemctl start ollama
```

Verifica:

```bash
curl http://localhost:11434/api/tags
```

## 3. Descargar el modelo

```bash
# Recomendado para Orange Pi Zero 3 (equilibrio velocidad/calidad)
ollama pull tinyllama:1.1b

# Alternativa más rápida (menor calidad)
ollama pull qwen2:0.5b

# Alternativa más precisa (más lenta, necesita más RAM)
ollama pull phi3:mini
```

## 4. Instalar el agente

```bash
git clone https://github.com/jqime/edge-sec-agent.git
cd edge-sec-agent
```

El agente usa **solo la biblioteca estándar de Python 3** — no requiere `pip install` de nada.

## 5. Primer uso

```bash
# Verificar que todo funciona
python3 src/agent.py --status

# Análisis de seguridad
python3 src/agent.py --security
```

## 6. Swap (recomendado)

Con modelos más grandes, añade swap para evitar OOM:

```bash
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

## Troubleshooting

### El agente se bloquea sin responder

```bash
systemctl restart ollama && sleep 25
python3 src/agent.py "hola"
```

Causa: un `Ctrl+C` previo dejó una petición pendiente en Ollama.

### El modelo tarda mucho en la primera respuesta

Normal en CPU sin GPU. TinyLlama tarda ~18–30 s en cargarse la primera vez.
Las siguientes llamadas son más rápidas (modelo en RAM).

### `ModuleNotFoundError: requests`

El agente v0.3+ usa `urllib` (stdlib). No necesita `requests`. Verifica que tienes la versión correcta:

```bash
head -3 src/agent.py
# Debe mostrar: import urllib.request
```

### Ver logs de Ollama en tiempo real

```bash
journalctl -fu ollama
```