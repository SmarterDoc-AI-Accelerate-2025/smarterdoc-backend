# -----------------------
# Base image
# -----------------------
FROM python:3.11-slim

# Install system deps (useful for networking/debug)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# -----------------------
# Install Python dependencies
# -----------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# -----------------------
# Copy application
# -----------------------
COPY app ./app
COPY .env.example .env

# -----------------------
# Runtime configuration
# -----------------------
ENV PYTHONUNBUFFERED=1
# Cloud Run injects $PORT automatically
EXPOSE 8080

# ✅ Use Cloud Run's provided $PORT (defaults to 8080 locally)
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
