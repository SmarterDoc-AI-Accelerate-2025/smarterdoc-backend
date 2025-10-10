# -----------------------
# Base image
# -----------------------
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# -----------------------
# Make sure Python can import from /app
# -----------------------
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

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
EXPOSE 8080

# ✅ Start FastAPI using the $PORT Cloud Run injects
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
