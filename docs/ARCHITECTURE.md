# Arquitectura y decisiones de diseño

## Por qué urllib en lugar de requests

Durante el desarrollo se detectó que `requests` con `stream=True` se bloquea
indefinidamente en Python 3.11 / urllib3 antiguo cuando Ollama tiene una
petición previa pendiente (por `Ctrl+C`). El módulo `urllib.request` de la
biblioteca estándar no tiene este problema y no añade dependencias externas.

## Por qué streaming

Sin streaming, el agente espera en silencio hasta 2 minutos. Con `stream=True`
los tokens aparecen en tiempo real, lo que da feedback visual inmediato aunque
el tiempo total sea el mismo.

## Por qué TinyLlama 1.1b

| Modelo | RAM | Tokens/s (OPi Zero 3) | Calidad |
|---|---|---|---|
| qwen2:0.5b | ~400 MB | ~0.7 | Aceptable |
| tinyllama:1.1b | ~637 MB | ~0.4 | Buena |
| phi3:mini | ~2.2 GB | ~0.1 | Excelente |

TinyLlama es el punto de equilibrio para 4 GB RAM con otros servicios corriendo.

## Flujo de una petición

```
usuario → agent.py
              │
              ├─ run_cmd(ss, free, hostname, lastb)  ← datos reales SO
              │
              ├─ construir prompt con contexto
              │
              └─ urllib.request.urlopen(stream=True)
                          │
                          ▼
                    Ollama :11434
                          │
                    TinyLlama 1.1b (CPU)
                          │
                    tokens → stdout en tiempo real
```

## Por qué no Docker para el agente

Los contenedores Docker en la Orange Pi Zero 3 añaden ~200 MB de RAM overhead.
El agente corre directamente en el SO para minimizar uso de recursos. Ollama ya
gestiona su propio ciclo de vida del modelo.

## Decisiones pendientes

- **v0.4:** ¿Demonio con `systemd` o bucle en `screen`? Se evaluará según
  estabilidad de Ollama en operación continua.
- **v0.5:** API REST — candidatos: `http.server` (stdlib) vs `FastAPI`
  (dependencia externa).