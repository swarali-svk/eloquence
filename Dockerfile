# Eloquence — TOEFL-style speaking assessment
FROM python:3.12-slim

# Keep Python output unbuffered and skip .pyc files.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code.
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Persist the SQLite DB in a mountable volume location.
RUN mkdir -p /app/data
ENV ELOQUENCE_DB=/app/data/eloquence.db

WORKDIR /app/backend
EXPOSE 8010

# Inference provider is chosen at runtime via env vars:
#   -e GROQ_API_KEY=...            -> uses Groq (fast cloud)
#   -e OLLAMA_HOST=http://host.docker.internal:11434  -> uses local Ollama on the host
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010"]
