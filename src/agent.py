#!/usr/bin/env python3
"""
Edge Sec Agent - Agente autónomo de IA para SecDevOps
"""

import subprocess
import requests
import sys
import time

class SecDevOpsAgent:
    def __init__(self):
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "tinyllama:1.1b"
    
    def ask(self, prompt):
        """Pregunta al modelo IA con timeout largo"""
        try:
            print("🤖 Generando respuesta... (puede tardar hasta 2 minutos)")
            response = requests.post(self.ollama_url, json={
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }, timeout=180)  # Aumentado a 180 segundos
            return response.json().get("response", "Error: No response")
        except requests.exceptions.Timeout:
            return "Error: Tiempo de espera agotado. El modelo tarda más de 3 minutos."
        except Exception as e:
            return f"Error conectando a Ollama: {e}"
    
    def execute(self, command):
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout
    
    def status(self):
        return {
            "model": self.model,
            "ip": self.execute("hostname -I").strip(),
            "uptime": self.execute("uptime -p").strip()
        }

if __name__ == "__main__":
    agent = SecDevOpsAgent()
    print("🦞 Edge Sec Agent - SecDevOps AI Assistant")
    print(f"📡 Modelo: {agent.model}")
    
    # Verificar conexión con Ollama
    try:
        test = requests.get("http://localhost:11434/api/tags", timeout=5)
        print("🌐 Ollama: ✅ Conectado")
    except:
        print("🌐 Ollama: ❌ No conectado")
    
    if len(sys.argv) > 1:
        pregunta = " ".join(sys.argv[1:])
        print(f"\n💬 Pregunta: {pregunta}")
        start = time.time()
        respuesta = agent.ask(pregunta)
        elapsed = time.time() - start
        print(f"🤖 Respuesta ({elapsed:.1f}s): {respuesta}")
    else:
        print("\n✅ Agente listo. Usa: python3 src/agent.py 'tu pregunta'")
