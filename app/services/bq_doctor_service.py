from google.cloud import bigquery
import json
from app.config import settings


class BQDoctorService:

    def __init__(self, client: bigquery.Client):
        self.client = client
        self.table = f"{settings.GCP_PROJECT_ID}.{settings.BQ_CURATED_DATASET}.{settings.BQ_PROFILES_TABLE}"

    def _ensure_list(self, v):
        if v is None: return []
        if isinstance(v, list): return v
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
        where = ["profile_picture_url IS NOT NULL"]
        params = []

        if specialty:
            where.append("LOWER(primary_specialty) LIKE LOWER(@specialty)")
            params.append(
                bigquery.ScalarQueryParameter("specialty", "STRING",
                                              f"%{specialty}%"))

        if min_experience is not None:
            where.append("SAFE_CAST(years_experience AS INT64) >= @min_exp")
            params.append(
                bigquery.ScalarQueryParameter("min_exp", "INT64",
                                              int(min_experience)))

        if has_certification:
            where.append("ARRAY_LENGTH(certifications) > 0")

        where_clause = " AND ".join(where)

        query = f"""
        SELECT
          CAST(npi AS STRING) AS npi,
          first_name,
          last_name,
          primary_specialty,
          SAFE_CAST(years_experience AS INT64) AS years_experience,
          bio AS bio,
          testimonial_summary_text,
          publications,
          certifications,
          education,
          hospitals,
          ratings,
          SAFE_CAST(latitude  AS FLOAT64)  AS latitude,
          SAFE_CAST(longitude AS FLOAT64)  AS longitude,
          address,                              
          profile_picture_url
        FROM `{self.table}`
        WHERE {where_clause}
        ORDER BY years_experience DESC NULLS LAST
        LIMIT @limit
        """

        params.append(
            bigquery.ScalarQueryParameter("limit", "INT64", int(limit)))
        job = self.client.query(
            query, job_config=bigquery.QueryJobConfig(query_parameters=params))
        rows = list(job)

        out = []
        for r in rows:
            d = dict(r)
            d["publications"] = self._ensure_list(d.get("publications"))
            d["certifications"] = self._ensure_list(d.get("certifications"))
            d["education"] = self._ensure_list(d.get("education"))
            d["hospitals"] = self._ensure_list(d.get("hospitals"))

            ratings = d.get("ratings")
            if isinstance(ratings, str):
                try:
                    ratings = json.loads(ratings)
                except Exception:
                    ratings = []
            d["ratings"] = ratings or []

            out.append(d)
        return out
