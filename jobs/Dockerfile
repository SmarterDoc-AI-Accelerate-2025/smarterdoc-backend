FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir google-cloud-bigquery requests

# Copy the backfill script into the image
COPY geocode_backfill.py /app/geocode_backfill.py

# Set entrypoint to run the job
ENTRYPOINT ["python", "/app/geocode_backfill.py"]

