#!/usr/bin/env python3
"""
wsgi.py - Punto de entrada WSGI para producción (Gunicorn/uWSGI).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.sec_web import app

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
