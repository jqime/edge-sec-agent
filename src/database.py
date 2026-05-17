#!/usr/bin/env python3
"""
database.py - Módulo de persistencia SQLite para métricas históricas del Edge Sec Agent.
Almacena: timestamp, cpu_usage, ram_usage, cpu_temp, banned_ips.
"""
import sqlite3, os
from datetime import datetime, timedelta

DB_PATH = os.environ.get("EDGE_DB_PATH", "/root/edge-sec-agent/data/edge_metrics.db")

def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def prune_old_metrics(days=30):
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_conn()
    deleted = conn.execute("DELETE FROM metrics WHERE timestamp < ?", (cutoff,)).rowcount
    conn.commit()
    conn.close()
    return deleted

def init_db():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            cpu_usage REAL,
            ram_usage REAL,
            cpu_temp REAL,
            banned_ips INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()
    prune_old_metrics(days=30)

def insert_metric(cpu_usage=None, ram_usage=None, cpu_temp=None, banned_ips=0):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO metrics (timestamp, cpu_usage, ram_usage, cpu_temp, banned_ips) VALUES (?,?,?,?,?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), cpu_usage, ram_usage, cpu_temp, banned_ips)
    )
    conn.commit()
    conn.close()

def get_metrics(limit=100, order="DESC"):
    conn = _get_conn()
    rows = conn.execute(f"SELECT * FROM metrics ORDER BY id {order} LIMIT ?", (int(limit),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_latest():
    conn = _get_conn()
    row = conn.execute("SELECT * FROM metrics ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None

# Auto-inicializar al importar
init_db()
