import os, time, math, json, random
from typing import List, Dict, Optional
import requests
from google.cloud import bigquery
from app.config import settings
from app.deps import get_bq_sync

BQ = get_bq_sync()
PROJECT = settings.GCP_PROJECT_ID or os.getenv("PROJECT_ID")
DATASET = settings.BQ_CURATED_DATASET or os.getenv("BQ_CURATED_DATASET",
                                                   "curated")
CACHE_TABLE = settings.BQ_GEO_CACHE_TABLE or os.getenv("BQ_GEO_CACHE_TABLE",
                                                       "_geocode_cache")
INPUT_TABLE = settings.BQ_GEO_INPUT_TABLE or os.getenv("BQ_GEO_CACHE_TABLE",
                                                       "_geocode_input")
API_KEY = settings.MAPS_API_KEY or os.getenv("MAPS_API_KEY")
QPS = float(os.getenv("QPS", "6"))
PAGE_SIZE = int(os.getenv("PAGE_SIZE", "1000"))
MAX_ROWS = int(os.getenv("MAX_ROWS", "20000"))  # safety cap per run
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "10"))

assert PROJECT and API_KEY, "PROJECT and MAPS_API_KEY are required"

TO_FETCH_SQL = f"""
SELECT i.latitude, i.longitude
FROM `{PROJECT}.{DATASET}.{INPUT_TABLE}` i
LEFT JOIN `{PROJECT}.{DATASET}.{CACHE_TABLE}` c
USING (latitude, longitude)
WHERE c.address IS NULL
LIMIT @limit OFFSET @offset
"""


def geocode(lat: float, lng: float) -> Optional[str]:
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"latlng": f"{lat},{lng}", "key": API_KEY}
    r = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
    data = r.json()
    status = data.get("status")
    if status == "OK" and data.get("results"):
        return data["results"][0]["formatted_address"]
    if status in ("ZERO_RESULTS", ):
        return None
    if status in ("OVER_QUERY_LIMIT", "RESOURCE_EXHAUSTED"):
        # exponential backoff
        time.sleep(2 + random.random())
    return None


def insert_batch(rows: List[Dict]):
    if not rows:
        return
    table_id = f"{PROJECT}.{DATASET}.{CACHE_TABLE}"
    # Make sure we always write a string (not NULL) to avoid repeated retries
    payload = [{
        "latitude": r["latitude"],
        "longitude": r["longitude"],
        "address": r.get("address") or "Unknown location"
    } for r in rows]
    errors = BQ.insert_rows_json(table_id, payload)
    if errors:
        # ignore duplicates; raise on real failures
        dupeish = all("duplicate" in str(e).lower() for e in errors)
        if not dupeish:
            raise RuntimeError(f"Insert errors: {errors}")


def run_once() -> int:
    processed = 0
    offset = 0
    min_interval = 1.0 / max(QPS, 0.1)
    while processed < MAX_ROWS:
        # Pull next page of “to geocode”
        job = BQ.query(
            TO_FETCH_SQL,
            job_config=bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter(
                    "limit", "INT64", min(PAGE_SIZE, MAX_ROWS - processed)),
                bigquery.ScalarQueryParameter("offset", "INT64", offset),
            ]))
        rows = list(job.result())
        if not rows:
            break

        batch = []
        last = 0.0
        for row in rows:
            # rate limit
            now = time.time()
            sleep_for = last + min_interval - now
            if sleep_for > 0:
                time.sleep(sleep_for)
            last = time.time()

            lat, lng = float(row["latitude"]), float(row["longitude"])
            addr = geocode(lat, lng)
            batch.append({"latitude": lat, "longitude": lng, "address": addr})

            # smaller flushes keep requests under size limits
            if len(batch) >= 200:
                insert_batch(batch)
                batch = []

        insert_batch(batch)
        got = len(rows)
        processed += got
        offset += got
    return processed


if __name__ == "__main__":
    total = run_once()
    print(json.dumps({"processed": total}, indent=2))
