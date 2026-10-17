# RAG ligero sobre los logs del Honeypot (Fase 2)

Consulta en lenguaje natural de los eventos de Cowrie usando generación aumentada por recuperación (RAG), **sin PyTorch** y **sin tocar la API de producción**.

## Decisión de diseño (por qué NO ChromaDB + sentence-transformers)

La Orange Pi Zero 3 tiene **3.9 GB de RAM y 0 swap** (ARM64). El plan inicial (ChromaDB + `sentence-transformers`) arrastra **PyTorch** (cientos de MB a disco y RAM alta en ARM64) y añade `onnxruntime`. Sumado a Ollama generando, con 0 swap, un OOM puede tumbar `edge-sec-agent` u Ollama.

Alternativa adoptada, mucho más ligera:

| Pieza | Elección | Motivo |
|---|---|---|
| Embeddings | **Ollama** `nomic-embed-text` (274 MB, 768 dims) | Reutiliza Ollama ya instalado; sin torch |
| Base vectorial | **SQLite + `sqlite-vec`** | SQLite ya está en el sistema; extensión diminuta |
| LLM | **`qwen2.5:1.5b`** (986 MB) | `tinyllama:1.1b` no era fiable para QA factual |

Consumo medido: pico ~3.0–3.4 GB usados, ~0.5–0.9 GB disponibles; **sin OOM**.

## Aislamiento

- Venv dedicado: `/opt/edge-sec-agent-rag/venv` (`requests`, `sqlite-vec`, `ollama`).
- **No toca** el venv de producción (`/opt/edge-sec-agent/venv`) ni `src/`.
- Script: `scripts/rag_query.py` (solo lectura del log; no escribe en producción).
- Base de datos: `/opt/edge-sec-agent-rag/cowrie_vec.db`.

## Puesta en marcha

```bash
python3 -m venv /opt/edge-sec-agent-rag/venv
/opt/edge-sec-agent-rag/venv/bin/pip install requests sqlite-vec ollama
ollama pull nomic-embed-text
ollama pull qwen2.5:1.5b
```

## Uso

```bash
# Indexar (re)genera la BD vectorial desde cowrie.json
/opt/edge-sec-agent-rag/venv/bin/python scripts/rag_query.py ingest

# Ver nº de eventos indexados
/opt/edge-sec-agent-rag/venv/bin/python scripts/rag_query.py stats

# Preguntar en lenguaje natural
/opt/edge-sec-agent-rag/venv/bin/python scripts/rag_query.py ask "¿De qué IP vienen los logins y qué comandos se ejecutaron?"
```

Variables de entorno:

| Variable | Default | Descripción |
|---|---|---|
| `COWRIE_LOG` | `/opt/cowrie/cowrie-git/var/log/cowrie/cowrie.json` | Log de eventos |
| `RAG_DB` | `/opt/edge-sec-agent-rag/cowrie_vec.db` | Base SQLite |
| `OLLAMA_EMBED` | `nomic-embed-text` | Modelo de embeddings |
| `RAG_LLM_MODEL` | `qwen2.5:1.5b` | Modelo de chat |
| `RAG_TOP_K` | `0` | Fragmentos semánticos (0 = solo digest, más rápido) |
| `RAG_MAX_TOKENS` | `220` | Tope de tokens generados |

## Cómo funciona

1. `ingest`: parsea `cowrie.json`, resume cada evento en una línea de texto, calcula su embedding con `nomic-embed-text` y lo guarda en una tabla `vec0` de `sqlite-vec`.
2. `ask`: además de la búsqueda semántica opcional, construye un **digest determinista** (conteos por IP, logins exitosos y comandos) a partir de los eventos reales. El LLM responde basándose en ese digest y los fragmentos recuperados.
3. La respuesta se genera con `qwen2.5:1.5b` vía Ollama.

## Evidencia (2026-10-17)

- `ingest`: **73 eventos** indexados; `cowrie_vec.db` = 3.1 MB; ~2 min (una llamada de embedding por evento, ~1.5 s c/u).
- Digest determinista (exacto): 4 logins exitosos (`127.0.0.1` ×2, `100.109.41.91`, `100.125.181.114`) y 4 comandos (`id`, `uname -a; id; echo pwned`, `ls -la`, `whoami`).
- `ask` (config por defecto, `RAG_TOP_K=0`, `RAG_MAX_TOKENS=220`): respuesta correcta con las **3 IPs** y los comandos reales; ~3 min.

## Limitaciones honestas

- **Rendimiento**: CPU pura a ~1.3 tok/s. Una respuesta tarda ~1.5–3 min. Es una herramienta de consulta diferida, **no** interactiva en tiempo real.
- **`tinyllama:1.1b` no sirve** para QA factual (dijo "3 logins" cuando eran 4). Se cambió a `qwen2.5:1.5b`.
- **Truncado**: con `RAG_MAX_TOKENS` bajo (p. ej. 120) la respuesta puede cortarse a media línea.
- **Prompt grande = lento**: la *prompt eval* en CPU domina; por eso el default usa `RAG_TOP_K=0` (solo digest). Subir el top-k añade fragmentos y dispara el tiempo.

## Estado

- Fase 2 (CLI aislado): **completada y validada**.
- Fase 3 (integración en `src/sec_web.py`, `/v1/chat/completions`): **pendiente de autorización del owner**. Requiere backup previo de `src/sec_web.py` y no se ha iniciado.
