FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8443

# Nota: Diseñado como entorno de simulación/QA agnóstico.
CMD ["gunicorn", "--bind", "127.0.0.1:5000", "wsgi:app"]
