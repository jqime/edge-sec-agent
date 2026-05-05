#!/usr/bin/env python3
from flask import Flask, jsonify
import subprocess, json
app = Flask(__name__)
@app.route("/api/metrics")
def metrics():
    out = subprocess.getoutput("/usr/local/bin/sec-agent --security --json")
    try: return jsonify(json.loads(out))
    except: return jsonify({"error":"no data"}), 500
@app.route("/")
def index():
    return "<html><body><h1>Edge Sec Agent Dashboard</h1><p><a href='/api/metrics'>/api/metrics</a></p></body></html>"
if __name__ == "__main__": app.run(host="0.0.0.0", port=8080)
