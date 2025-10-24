from google.cloud import bigquery
import json
from app.config import settings
from typing import Generator, Dict, Any, List
import time
from app.util.logging import logger
import datetime
import asyncio
from app.models.schemas import DoctorOut


class BQDoctorService:

    def __init__(self, client: bigquery.Client):
        self.client = client
        # Resolve project id robustly: prefer explicit BQ project, then global GCP project, then client project
        project_id = (settings.BQ_PROJECT or settings.GCP_PROJECT_ID
                      or getattr(client, "project", None))
        if not project_id:
            try:
                # Final fallback to ADC
                from google.auth import default as _google_auth_default
                _, detected_project = _google_auth_default()
                project_id = detected_project
            except Exception:
                project_id = None
        # Update global settings if it was unset to avoid future None usage
        if not settings.GCP_PROJECT_ID and project_id:
            try:
                # pydantic BaseSettings fields are mutable at runtime in this app
                settings.GCP_PROJECT_ID = project_id  # type: ignore[attr-defined]
            except Exception:
                pass
        self.table = f"{project_id}.{settings.BQ_CURATED_DATASET}.{settings.BQ_PROFILES_TABLE}"

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
        where = [
            "profile_picture_url IS NOT NULL AND TRIM(profile_picture_url) != ''",
            "primary_specialty IS NOT NULL AND TRIM(primary_specialty) != ''",
            "bio IS NOT NULL AND TRIM(bio) != ''",
            "testimonial_summary_text IS NOT NULL AND TRIM(testimonial_summary_text) != ''"
        ]
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
                WITH DedupedFilteredDoctors AS (
                    SELECT
                        *,
                        ROW_NUMBER() OVER(
                            PARTITION BY npi
                            ORDER BY updated_at DESC, npi DESC 
                        ) AS rn
                    FROM `{self.table}`
                    WHERE {where_clause} 
                )
                SELECT
                    -- Select all the final columns required by the application schema
                    CAST(npi AS STRING) AS npi,
                    first_name,
                    last_name,
                    primary_specialty,
                    SAFE_CAST(years_experience AS INT64) AS years_experience,
                    bio,
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
                FROM DedupedFilteredDoctors
                WHERE rn = 1
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

    def fetch_doctors_for_indexing(
            self) -> Generator[Dict[str, Any], None, None]:
        """
        Fetches doctor data from BQ, filtering for those with a profile picture,
        distinct NPI, and ordered by date (only gets the latest)
        Yields results row-by-row.
        """

        query = f"""
            WITH DedupedDoctors AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER(
                        PARTITION BY npi
                        ORDER BY updated_at DESC, npi DESC  -- Prioritize the latest record
                    ) AS rn
                FROM
                    `{self.table}`
                WHERE
                    profile_picture_url IS NOT NULL
                    AND TRIM(profile_picture_url) != ''
                    -- START OF CRITICAL CHANGE: Filter by recently updated records
                    AND updated_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 10 HOUR)
            )
            SELECT
                npi,
                primary_specialty,
                bio,
                testimonial_summary_text,
                publications,
                certifications,
                education,
                hospitals,
                first_name,
                last_name
            FROM
                DedupedDoctors
            WHERE
                rn = 1
                -- OPTIONAL: Add a secondary filter here if you want to be extra safe 
                -- and exclude any rows that were already re-indexed recently.
                -- For now, the TIMESTAMP_SUB filter in the CTE is sufficient.
        """
        logger.info(f"Executing BQ fetch query: {query}")

        query_job = self.client.query(query)

        # Iterate over results and yield as dictionaries
        for row in query_job:
            yield dict(row.items())

    def upsert_vectors(self,
                       records: List[Dict[str, Any]],
                       attribute: str,
                       type: str,
                       mode='REPEATED'):
        """
        Upserts (updates) the doctor records in BigQuery based on NPI, 
        only modifying the bio_vector and updated_at columns.
        """
        if not records:
            return
        PROJECT_ID = settings.GCP_PROJECT_ID
        DATASET_ID = settings.BQ_CURATED_DATASET
        TABLE_ID = settings.BQ_PROFILES_TABLE

        try:
            table_ref = self.client.dataset(DATASET_ID).table(TABLE_ID)
            table_obj = self.client.get_table(table_ref)
            # Check if the attribute is in the existing table schema
            if not any(field.name == attribute for field in table_obj.schema):
                logger.info(
                    f"Column '{attribute}' not found in {self.table}. Adding it now..."
                )
                if type.upper() == "STRUCT":
                    # Full BigQuery STRUCT definition for a sparse vector
                    bq_type_string = "STRUCT<dimensions ARRAY<INT64>, values ARRAY<FLOAT64>>"
                elif mode.upper() == "REPEATED":
                    # Array type (e.g., FLOAT64 array for dense vectors)
                    bq_type_string = f"ARRAY<{type}>"
                else:
                    # Simple single field type
                    bq_type_string = type
                # Use ALTER TABLE to add the column
                alter_query = f"""
                    ALTER TABLE `{self.table}`
                    ADD COLUMN {attribute} {bq_type_string};
                """
                alter_job = self.client.query(alter_query)
                alter_job.result()
                logger.info(
                    f"Successfully added column '{attribute}' to {self.table}."
                )
            else:
                logger.debug(
                    f"Column '{attribute}' already exists in {self.table}.")
        except Exception as e:
            # Handle cases where table might not exist or other errors
            logger.error(f"Error during schema check/modification: {e}")

        # 1. Create a temporary staging table to hold the new vector data
        temp_table_name = f"{settings.BQ_PROFILES_TABLE}_staging_{time.time_ns()}"
        # temp_table_id = f"`{settings.BQ_PROFILES_TABLE}.{temp_table_name}`"
        temp_table_load_id = f"{PROJECT_ID}.{DATASET_ID}.{temp_table_name}"

        schema_fields = [
            bigquery.SchemaField("npi", "INT64"),
        ]
        if type.upper() == "STRUCT":
            # This handles the sparse vector (RECORD/STRUCT)
            vector_schema_field = bigquery.SchemaField(
                name=attribute,
                field_type="STRUCT",
                mode="NULLABLE",  # STRUCT is typically nullable
                fields=
                [  # Nested schema definition is mandatory for STRUCT/RECORD
                    bigquery.SchemaField("dimensions",
                                         "INT64",
                                         mode="REPEATED"),
                    bigquery.SchemaField("values", "FLOAT64", mode="REPEATED"),
                ])
        else:
            # This handles DENSE vectors (FLOAT64 array)
            vector_schema_field = bigquery.SchemaField(
                name=attribute,
                field_type=type,
                mode=mode,  # This will be 'REPEATED' for a dense vector array
            )

        schema_fields.append(vector_schema_field)
        schema_fields.append(bigquery.SchemaField("updated_at", "TIMESTAMP"))

        job_config = bigquery.LoadJobConfig(
            schema=schema_fields,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )

        # Prepare data for insertion (BigQuery client requires specific format)
        rows_to_insert = []

        for r in records:
            rows_to_insert.append({
                "npi":
                r['npi'],
                attribute:
                r[attribute],
                "updated_at":
                datetime.datetime.now().isoformat()
            })

        # Insert data into the staging table
        load_job = self.client.load_table_from_json(rows_to_insert,
                                                    temp_table_load_id,
                                                    job_config=job_config)
        load_job.result()  # Wait for job to complete

        # 2. Execute the MERGE statement to perform the upsert
        merge_query = f"""
            MERGE INTO `{self.table}` AS T
            USING `{temp_table_load_id}` AS S
            ON T.npi = S.npi
            WHEN MATCHED THEN
              UPDATE SET 
                T.{attribute} = S.{attribute},
                T.updated_at = S.updated_at;
        """

        merge_job = self.client.query(merge_query)
        merge_job.result()
        logger.info(
            f"Successfully merged {len(records)} records into {self.table}.")

        # 3. Clean up the temporary staging table
        self.client.delete_table(temp_table_load_id)
        logger.debug(f"Cleaned up staging table {temp_table_load_id}.")

    async def fetch_full_profiles_by_npi(
            self, npi_list: List[str]) -> List[Dict[str, Any]]:
        """
            Fetches the complete doctor profiles from BigQuery for a given list of NPIs.
            This is the CRITICAL enrichment step after vector search returns only NPIs/scores.
            
            Args:
                npi_list: List of NPI strings returned by the Vector Search Endpoint.
                
            Returns:
                A list of full doctor profile dictionaries.
            """
        if not npi_list:
            return []

        # 1. Prepare the list of NPIs for the SQL IN clause
        # The list must be converted to a comma-separated string of quoted values.
        npi_in_clause = ", ".join([f"'{npi}'" for npi in npi_list])

        # 2. Define the BigQuery SQL Query
        # This query selects all necessary columns for the front-end display and the LLM re-ranking (Stage 3).
        query = f"""
                WITH DedupedFilteredDoctors AS (
                    SELECT
                        *,
                        ROW_NUMBER() OVER(
                            PARTITION BY npi
                            ORDER BY updated_at DESC, npi DESC 
                        ) AS rn
                    FROM `{self.table}`
                    WHERE 
                        CAST(npi AS STRING) IN ({npi_in_clause})
                )
                SELECT
                    -- Select ALL the columns required by the application and re-ranker
                    CAST(npi AS STRING) AS npi,
                    first_name,
                    last_name,
                    primary_specialty,
                    SAFE_CAST(years_experience AS INT64) AS years_experience,
                    bio,
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
                FROM DedupedFilteredDoctors
                WHERE rn = 1
            """

        logger.info(f"Executing BQ lookup for {len(npi_list)} NPIs.")

        # 3. Execute the query
        # Since this is an async function, we should use an executor for the synchronous BQ client call.
        try:
            loop = asyncio.get_event_loop()

            job = await loop.run_in_executor(None, self.client.query, query)
            rows = list(job.result())
        except Exception as e:
            logger.error(
                f"BQ lookup failed during fetch_full_profiles_by_npi: {e}")
            return []

        # 4. Process and format results
        out = []
        for r in rows:
            d = dict(r)
            # Apply cleaning/conversion helper functions
            d["publications"] = self._ensure_list(d.get("publications"))
            d["certifications"] = self._ensure_list(d.get("certifications"))
            d["education"] = self._ensure_list(d.get("education"))
            d["hospitals"] = self._ensure_list(d.get("hospitals"))

            # Process ratings field if it's a JSON string
            ratings = d.get("ratings")
            if isinstance(ratings, str):
                try:
                    ratings = json.loads(ratings)
                except Exception:
                    ratings = []
            d["ratings"] = ratings or []

            out.append(d)

        logger.info(f"Successfully retrieved {len(out)} full profiles.")
        return out

    async def get_agent_recommended_doctors(self, request_data: Dict[str,
                                                                     Any]):
        """
            [WRAPPER] Calls the RagAgentService to get the final, ranked list.
        """

        from app.services.rag_agent_service import RagAgentService
        from app.deps import get_gemini_client, get_vector_search_service
        # get singletons
        gemini_client_instance = get_gemini_client()
        vector_search_service_instance = get_vector_search_service()

        rag_agent = RagAgentService(
            vector_search_service=vector_search_service_instance,
            gemini_client=gemini_client_instance)

        fields_dict = DoctorOut.model_fields
        DOCTOR_FIELDS = list(fields_dict.keys())

        selected = await rag_agent.get_recommended_doctors(request_data)

        cleaned_output = [{
            key: doc.get(key)
            for key in DOCTOR_FIELDS if key in doc
        } for doc in selected]

        return cleaned_output

    def get_all_specialties(self):
        """
        Query BigQuery to get all distinct specialties from the doctor profiles table.
        Returns a sorted list of unique specialties where primary_specialty is not null.
        """
        query = f"""
        SELECT DISTINCT primary_specialty
        FROM `{self.table}`
        WHERE primary_specialty IS NOT NULL 
          AND primary_specialty != ''
        ORDER BY primary_specialty ASC
        """

        job = self.client.query(query)
        rows = list(job)

        # Extract specialty strings from rows
        specialties = [
            row.primary_specialty for row in rows if row.primary_specialty
        ]
        return specialties
