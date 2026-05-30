#!/usr/bin/env python3
"""
wsgi.py — Punto de entrada WSGI para producción (Gunicorn/uWSGI).
"""
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from src.sec_web import app

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
