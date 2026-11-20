#!/usr/bin/env python3
"""RAG ligero sobre los logs del honeypot Cowrie (Fase 2, aislado).

NO forma parte de la API de producción (src/). Se ejecuta con el venv
dedicado /opt/edge-sec-agent-rag/venv, que incluye sqlite-vec y el cliente
ollama. Usa Ollama (modelo de embeddings + LLM) en lugar de PyTorch para no
comprometer la RAM de la Orange Pi (0 swap).

Uso:
    rag_query.py ingest            # (re)indexa cowrie.json en la BD vectorial
    rag_query.py ask "pregunta"    # recupera eventos y pregunta al LLM
    rag_query.py stats             # nº de eventos indexados

Variables de entorno:
    COWRIE_LOG       ruta al cowrie.json (default /opt/cowrie/.../cowrie.json)
    RAG_DB           ruta a la base SQLite (default /opt/edge-sec-agent-rag/cowrie_vec.db)
    OLLAMA_EMBED     modelo de embeddings (default nomic-embed-text)
    RAG_LLM_MODEL    modelo de chat (default tinyllama:1.1b)
    RAG_TOP_K        nº de fragmentos semánticos (default 0 = solo digest, más rápido)
    RAG_LLM_MODEL    modelo de chat (default qwen2.5:1.5b)
    RAG_MAX_TOKENS   tope de tokens a generar (default 220; CPU ~1.3 tok/s)
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

import ollama
import sqlite_vec

_DEFAULT_COWRIE_LOG = "/opt/cowrie/cowrie-git/var/log/cowrie/cowrie.json"
_DEFAULT_DB = "/opt/edge-sec-agent-rag/cowrie_vec.db"
_EMBED_DIM = 768
_FIELDS = ("eventid", "src_ip", "username", "password", "input", "version", "timestamp")


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value else default


def _log_path() -> str:
    return _env("COWRIE_LOG", _DEFAULT_COWRIE_LOG)


def _db_path() -> str:
    return _env("RAG_DB", _DEFAULT_DB)


def connect_db() -> sqlite3.Connection:
    db_file = _db_path()
    Path(db_file).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_file)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    return db


def recreate_schema(db: sqlite3.Connection) -> None:
    db.execute("DROP TABLE IF EXISTS events")
    db.execute(
        "CREATE VIRTUAL TABLE events USING vec0("
        "embedding float[768], "
        "+eventid text, +src_ip text, +ts text, +content text)"
    )
    db.commit()


def read_events(path: str) -> list[dict]:
    events: list[dict] = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue
    except FileNotFoundError:
        sys.exit(f"[rag_query][ERROR] log no encontrado: {path}")
    return events


def event_to_text(event: dict) -> str:
    parts = [f"[{event.get('timestamp', '?')}] {event.get('eventid', '?')}"]
    for field in ("src_ip", "username", "password", "input", "version"):
        value = event.get(field)
        if value:
            parts.append(f"{field}={value}")
    return " ".join(parts)


def embed(text: str) -> list[float]:
    model = _env("OLLAMA_EMBED", "nomic-embed-text")
    response = ollama.embeddings(model=model, prompt=text)
    return response["embedding"]


def cmd_ingest(_args: argparse.Namespace) -> None:
    path = _log_path()
    events = read_events(path)
    if not events:
        sys.exit(f"[rag_query] sin eventos en {path}")
    db = connect_db()
    recreate_schema(db)
    indexed = 0
    for event in events:
        text = event_to_text(event)
        if not text.strip():
            continue
        vector = embed(text)
        db.execute(
            "INSERT INTO events(embedding, eventid, src_ip, ts, content) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                sqlite_vec.serialize_float32(vector),
                str(event.get("eventid", "")),
                str(event.get("src_ip", "")),
                str(event.get("timestamp", "")),
                text,
            ),
        )
        indexed += 1
    db.commit()
    db.close()
    print(f"[rag_query] indexados {indexed} eventos de {path}")


def cmd_stats(_args: argparse.Namespace) -> None:
    db = connect_db()
    try:
        total = db.execute("SELECT count(*) FROM events").fetchone()[0]
    except sqlite3.OperationalError:
        total = 0
    db.close()
    print(f"[rag_query] eventos indexados: {total} | db={_db_path()}")


def build_digest(events: list[dict]) -> str:
    ip_counts: dict[str, int] = {}
    for event in events:
        ip = str(event.get("src_ip", "?"))
        ip_counts[ip] = ip_counts.get(ip, 0) + 1
    lines = ["RESUMEN REAL DEL HONEYPOT:"]
    lines.append(
        "Eventos por IP: " + ", ".join(f"{ip}={c}" for ip, c in sorted(ip_counts.items()))
    )
    logins = [e for e in events if e.get("eventid") == "cowrie.login.success"]
    if logins:
        lines.append("Logins exitosos:")
        for e in logins:
            lines.append(
                f"  - {e.get('timestamp')} ip={e.get('src_ip')} "
                f"user={e.get('username')} pass={e.get('password')}"
            )
    commands = [e for e in events if e.get("eventid") == "cowrie.command.input"]
    if commands:
        lines.append("Comandos ejecutados:")
        for e in commands:
            lines.append(f"  - {e.get('timestamp')} ip={e.get('src_ip')} input={e.get('input')}")
    return "\n".join(lines)


def retrieve(question: str, k: int) -> list[str]:
    db = connect_db()
    try:
        rows = db.execute(
            "SELECT eventid, src_ip, ts, content, distance FROM events "
            "WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
            (sqlite_vec.serialize_float32(embed(question)), k),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        db.close()
        sys.exit(f"[rag_query][ERROR] índice vacío o inválido ({exc}); ejecuta 'ingest'")
    db.close()
    return [row[3] for row in rows]


def cmd_ask(args: argparse.Namespace) -> None:
    question = args.question
    k = int(_env("RAG_TOP_K", "0"))
    events = read_events(_log_path())
    digest = build_digest(events)
    contexts = retrieve(question, k) if k > 0 else []
    if not contexts and not digest.strip():
        sys.exit("[rag_query] sin datos; ejecuta 'ingest' primero")
    model = _env("RAG_LLM_MODEL", "qwen2.5:1.5b")
    system = (
        "Eres un analista de ciberseguridad. Responde en español, en un máximo de 4 frases, "
        "usando SOLO el RESUMEN y los fragmentos. Enumera TODAS las IPs y TODOS los comandos "
        "relevantes que aparezcan. Si no hay datos suficientes, dilo. No inventes nada."
    )
    user = (
        f"{digest}\n\nFragmentos relevantes:\n"
        + "\n".join(f"- {c}" for c in contexts)
        + f"\n\nPregunta: {question}"
    )
    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        options={"num_predict": int(_env("RAG_MAX_TOKENS", "220")), "temperature": 0.2},
    )
    print(response["message"]["content"].strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG ligero sobre logs de Cowrie")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ingest", help="(re)indexa el log en la BD vectorial")
    sub.add_parser("stats", help="muestra el nº de eventos indexados")
    ask = sub.add_parser("ask", help="pregunta al LLM sobre los eventos")
    ask.add_argument("question", help="pregunta en lenguaje natural")
    args = parser.parse_args()

    handlers = {"ingest": cmd_ingest, "stats": cmd_stats, "ask": cmd_ask}
    handlers[args.command](args)


if __name__ == "__main__":
    main()
