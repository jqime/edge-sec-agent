#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
database.py — Módulo de persistencia SQLite unificado para Edge Sec Agent.
Almacena métricas de seguridad, hardware y rendimiento en una sola tabla.
Usado por agent.py (CLI) y sec_web.py (API).
"""
import sqlite3
import os
import logging
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger("edge-sec-agent.db")

DB_PATH = os.environ.get(
    "EDGE_DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "history.db"),
)


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _migrate_schema() -> None:
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='metrics'"
        )
        if not cursor.fetchone():
            return

        cursor = conn.execute("PRAGMA table_info(metrics)")
        existing = {row[1] for row in cursor.fetchall()}

        new_columns: dict[str, str] = {
            "score": "INTEGER",
            "ssh_failures": "INTEGER",
            "open_ports": "TEXT",
            "cpu_temp": "REAL",
            "ram_percent": "REAL",
            "cpu_usage": "REAL",
            "banned_ips": "INTEGER DEFAULT 0",
        }
        for col, col_type in new_columns.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE metrics ADD COLUMN {col} {col_type}")
                logger.info("Columna añadida a metrics: %s %s", col, col_type)
        conn.commit()
    except sqlite3.Error as exc:
        logger.error("Error en migración de schema: %s", exc)
    finally:
        conn.close()


def init_db() -> None:
    conn = _get_conn()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                score INTEGER,
                ssh_failures INTEGER,
                open_ports TEXT,
                cpu_temp REAL,
                ram_percent REAL,
                cpu_usage REAL,
                banned_ips INTEGER DEFAULT 0
            )
            """
        )
        conn.commit()
        _migrate_schema()
        prune_old_metrics(days=30)
        logger.info("Base de datos inicializada: %s", DB_PATH)
    except sqlite3.Error as exc:
        logger.error("Error al inicializar la BD: %s", exc)
        raise
    finally:
        conn.close()


def insert_metric(
    score: int | None = None,
    ssh_failures: int | None = None,
    open_ports: str | None = None,
    cpu_temp: float | None = None,
    ram_percent: float | None = None,
    cpu_usage: float | None = None,
    banned_ips: int = 0,
) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO metrics
                (timestamp, score, ssh_failures, open_ports, cpu_temp, ram_percent, cpu_usage, banned_ips)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                score,
                ssh_failures,
                open_ports,
                cpu_temp,
                ram_percent,
                cpu_usage,
                banned_ips,
            ),
        )
        conn.commit()
    except sqlite3.Error as exc:
        logger.error("Error al insertar métrica: %s", exc)
        raise
    finally:
        conn.close()


def get_metrics(limit: int = 100, order: str = "DESC") -> list[dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            f"SELECT * FROM metrics ORDER BY id {order} LIMIT ?",
            (int(limit),),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as exc:
        logger.error("Error al leer métricas: %s", exc)
        return []
    finally:
        conn.close()


def get_latest() -> dict[str, Any] | None:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM metrics ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    except sqlite3.Error as exc:
        logger.error("Error al leer última métrica: %s", exc)
        return None
    finally:
        conn.close()


def get_last_days_scores(days: int = 7) -> list[dict[str, Any]]:
    start = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT date(timestamp) AS day, AVG(score) AS avg_score
            FROM metrics
            WHERE date(timestamp) >= ? AND score IS NOT NULL
            GROUP BY day ORDER BY day ASC
            """,
            (start,),
        ).fetchall()
        return [
            {"date": day, "score": int(avg_score)}
            for day, avg_score in rows
            if avg_score is not None
        ]
    except sqlite3.Error as exc:
        logger.error("Error al leer histórico de scores: %s", exc)
        return []
    finally:
        conn.close()


def prune_old_metrics(days: int = 30) -> int:
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_conn()
    try:
        deleted = conn.execute(
            "DELETE FROM metrics WHERE timestamp < ?", (cutoff,)
        ).rowcount
        conn.commit()
        if deleted:
            logger.info("Podadas %d métricas anteriores a %s días", deleted, days)
        return deleted or 0
    except sqlite3.Error as exc:
        logger.error("Error al podar métricas viejas: %s", exc)
        return 0
    finally:
        conn.close()


init_db()
