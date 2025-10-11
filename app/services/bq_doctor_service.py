from google.cloud import bigquery
from app.config import settings


class BQDoctorService:

    def __init__(self):
        self.client = bigquery.Client(project=settings.GCP_PROJECT_ID)
        self.table = f"{settings.GCP_PROJECT_ID}.{settings.BQ_CURATED_DATASET}.{settings.BQ_PROFILES_TABLE}"

    def _ensure_list(self, v):
        # BigQuery may store these as STRING (JSON/text) or ARRAY<STRING>.
        if v is None:
            return []
        if isinstance(v, list):
            return v
        # Try to parse JSON array string; else wrap as single-item list
        try:
            import json
            parsed = json.loads(v)
            return parsed if isinstance(parsed, list) else [str(v)]
        except Exception:
            return [str(v)]

    def search_doctors(self,
                       specialty=None,
                       min_experience=None,
                       has_certification=False,
                       limit=30):
        filters = ["profile_picture_url IS NOT NULL"]
        if specialty:
            filters.append(
                f"LOWER(primary_specialty) LIKE '%{specialty.lower()}%'")
        if min_experience is not None:
            filters.append(
                f"SAFE_CAST(years_experience AS INT64) >= {int(min_experience)}"
            )
        if has_certification:
            filters.append("ARRAY_LENGTH(certifications) > 0")

        where_clause = " AND ".join(filters)
        query = f"""
        SELECT
          CAST(npi AS STRING) AS npi,
          first_name, last_name, primary_specialty,
          SAFE_CAST(years_experience AS INT64) AS years_experience,
          certifications, hospitals, profile_picture_url
        FROM `{self.table}`
        WHERE {where_clause}
        ORDER BY years_experience DESC NULLS LAST
        LIMIT {int(limit)}
        """
        rows = list(self.client.query(query))
        results = []
        for r in rows:
            d = dict(r)
            # Normalize types for Pydantic
            d["npi"] = str(d.get("npi")) if d.get("npi") is not None else None
            d["certifications"] = self._ensure_list(d.get("certifications"))
            d["hospitals"] = self._ensure_list(d.get("hospitals"))
            results.append(d)
        return results


bq_doctor_service = BQDoctorService()
