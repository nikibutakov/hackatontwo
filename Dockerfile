# ============================================================
# Образ бэкенда + фронтенда (CPU-режим).
# ВАЖНО: для живого демо на GPU запускайте нативно (не в Docker):
#   pip install -r requirements.txt -r ml/requirements-ml.txt
#   uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
# Docker здесь — для переносимости и CPU-запасного варианта.
# ============================================================
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY ml/metrics.json ./ml/metrics.json

EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
