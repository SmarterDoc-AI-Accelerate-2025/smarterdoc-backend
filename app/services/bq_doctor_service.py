from google.cloud import bigquery
import json
from app.config import settings


class BQDoctorService:

    def __init__(self, client: bigquery.Client):
        self.client = client
        self.table = f"{settings.GCP_PROJECT_ID}.{settings.BQ_CURATED_DATASET}.{settings.BQ_PROFILES_TABLE}"

    def _ensure_list(self, v):
        if v is None:
            return []
        if isinstance(v, list):
            return v
        # Some columns may be stored as STRING containing JSON arrays — handle both
        try:
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
          first_name, last_name,
          primary_specialty,
          SAFE_CAST(years_experience AS INT64) AS years_experience,
          -- NEW fields
          bio AS bio,                                     -- TEXT
          testimonial_summary_text,                       -- TEXT
          publications,                                   -- ARRAY<STRING> or STRING(JSON)
          certifications,                                 -- ARRAY<STRING>
          education,                                      -- ARRAY<STRING> or STRING(JSON)
          hospitals,                                      -- ARRAY<STRING> or STRING(JSON)
          ratings,                                        -- ARRAY<STRUCT> or STRING(JSON) (depends on your schema)
          SAFE_CAST(latitude  AS FLOAT64) AS latitude,
          SAFE_CAST(longitude AS FLOAT64) AS longitude,
          profile_picture_url
        FROM `{self.table}`
        WHERE {where_clause}
        ORDER BY years_experience DESC NULLS LAST
        LIMIT {int(limit)}
        """

        rows = list(self.client.query(query))
        out = []
        for r in rows:
            d = dict(r)

            # Normalize types that might be STRING(JSON) in some rows
            d["publications"] = self._ensure_list(d.get("publications"))
            d["certifications"] = self._ensure_list(d.get("certifications"))
            d["education"] = self._ensure_list(d.get("education"))
            d["hospitals"] = self._ensure_list(d.get("hospitals"))

            # If ratings is stored as JSON string, convert to dicts; otherwise pass-through
            ratings = d.get("ratings")
            if isinstance(ratings, str):
                try:
                    ratings = json.loads(ratings)
                except Exception:
                    ratings = []
            d["ratings"] = ratings or []

            out.append(d)
        return out
