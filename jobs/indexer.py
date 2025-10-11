# jobs/indexer.py

import asyncio
import datetime
import json
from typing import List, Dict, Any, Tuple
import os
from google.cloud import bigquery
from app.config import settings
from app.services.gemini_client import GeminiClient
from app.services.web_search import web_search_client, WebSearchClient
from app.deps import get_bq_sync
import time

BQ_CLIENT = get_bq_sync()
GEMINI_CLIENT = GeminiClient()

OUT_DIR = os.environ.get("INDEXER_OUT_DIR", "./out")
os.makedirs(OUT_DIR, exist_ok=True)


def _timestamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def save_payload_jsonl(enriched_data: List[Dict[str, Any]]) -> str:
    """
    Saves each record on its own line (JSONL) so it scales and is easy to resume.
    Returns the file path.
    """
    fn = os.path.join(OUT_DIR, f"enriched_doctors_{_timestamp()}.jsonl")
    with open(fn, "w", encoding="utf-8") as f:
        for row in enriched_data:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"-> Saved enriched payload to {fn}")
    return fn


def load_jsonl(filepath: str) -> List[Dict[str, Any]]:
    data = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    print(f"-> Loaded {len(data)} records from {filepath}")
    return data


# Extraction
def get_doctors_for_enrichment(limit: int = 1000) -> List[Dict[str, Any]]:
    """
    Pulls raw doctor data from the Fivetran-loaded table in BigQuery.
    Extracts structured fields from the raw JSON column for processing.
    """
    raw_table = f"{settings.BQ_RAW_DATASET}.{settings.BQ_RAW_TABLE}"

    query = f"""
    SELECT
        JSON_EXTRACT_SCALAR(_data, '$.number') AS npi,
        JSON_EXTRACT_SCALAR(_data, '$.basic.first_name') AS first_name,
        JSON_EXTRACT_SCALAR(_data, '$.basic.last_name') AS last_name,
        
        -- Primary Specialty Extraction (Robust Logic)
        COALESCE(
            (
                SELECT 
                    JSON_EXTRACT_SCALAR(t, '$.desc')
                FROM 
                    UNNEST(JSON_EXTRACT_ARRAY(_data, '$.taxonomies')) AS t 
                WHERE 
                    JSON_EXTRACT_SCALAR(t, '$.primary') = 'true'
                LIMIT 1
            ),
            JSON_EXTRACT_SCALAR(JSON_EXTRACT_ARRAY(_data, '$.taxonomies')[OFFSET(0)], '$.desc')
        ) AS primary_specialty
        
    FROM
        `{settings.GCP_PROJECT_ID}.{raw_table}`
    WHERE _fivetran_synced > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY) 
    LIMIT {limit}
    """

    try:
        print(f"Executing BQ query against {raw_table}...")
        query_job = BQ_CLIENT.query(query)
        results = [dict(row) for row in query_job]
        print(f"-> Retrieved {len(results)} doctors for enrichment.")
        return results
    except Exception as e:
        print(f"ERROR in BigQuery Extract: {e}")
        return []


# Transform


async def enrich_single_doctor(
        doctor: Dict[str, Any],
        use_custom_search: bool = False) -> Dict[str, Any]:
    """
    Handles the sequential, high-latency enrichment steps for one doctor.
    Returns a final_record dictionary ready for BigQuery insertion.
    """

    name = f"{doctor['first_name']} {doctor['last_name']}"
    specialty = doctor.get('primary_specialty', 'Physician')

    raw_bio_text = ""
    vector_result = [0.0] * 768  #fallback vector

    # default: using built-in grounding from LLM
    if not use_custom_search:
        prompt = (
            f"""As a medical data expert, find the official profile and review information for 
    Dr. {name}, a specialist in {specialty}. Extract their years of experience, 
    average patient ratings, certifications, education, hospital affiliations, and key publications.
    For the 'education' list, include the names of ALL medical schools, residencies, and fellowships.
    For the 'hospitals' list, include the names of ALL hospital and major clinical affiliations.
    For example:
        Dr. Jane Smith (Cardiology)
        education: ["Harvard Medical School (MD, 2005)", "Massachusetts General Hospital (Residency)"]
        hospitals: ["Massachusetts General Hospital", "Brigham and Women's Hospital"]
        certifications: ["Board Certified in Cardiology"]
        years_experience: 18
        average_rating: 4.7
        publications: ["Cardiac Outcomes in Post-Surgical Patients", "Advances in Echocardiography"]

    Now, repeat this process for Dr. {name}.
    Find the doctor's primary practice location and use Google Search to find its **precise latitude and longitude coordinates**.
    
    Summarize key patient testimonials to help new patients make informed decisions.
    
    Use Google Search as your tool. Calculate years of experience from their graduation or residency end date."""
        )

        # The grounding client returns a Tuple: (extracted_dict, sources_list)
        result_tuple = GEMINI_CLIENT.extract_structured_data_with_grounding(
            prompt_instruction=prompt)

        extracted_dict, sources = result_tuple

        text_to_embed = extracted_dict.get('bio_text_consolidated', "")

    else:
        # fallback: custom web search
        if not isinstance(web_search_client, WebSearchClient):
            print(
                f"Warning: custom search client not initialized correctly. Skipping NPI {doctor['npi']}."
            )
            return {
                **doctor, "updated_at": datetime.datetime.now().isoformat()
            }

        # Note: This is an awaitable call to the custom search client
        raw_bio_text, profile_url, review_snippets = await web_search_client.search_and_extract_bio(
            doctor)

        prompt = (
            f"Analyze the following consolidated web text and extract the structured data. "
            f"Consolidated Text: ---START--- {raw_bio_text} ---END---")
        extracted_dict = GEMINI_CLIENT.extract_structured_data(
            unstructured_text=prompt)

        if extracted_dict:
            extracted_dict['profile_picture_url'] = profile_url

        # The bio text for embedding comes from the custom web search
        text_to_embed = extracted_dict.get('bio_text_consolidated',
                                           raw_bio_text)
        sources = []  # No grounding metadata when using custom search

    # Error Handling & Vectorization
    if not extracted_dict:
        print(
            f"Warning: Failed to enrich NPI {doctor['npi']} using {'Grounding' if not use_custom_search else 'Custom Search'}. Returning raw data."
        )
        return {**doctor, "updated_at": datetime.datetime.now().isoformat()}

    if text_to_embed:
        # Call the actual implementation (returns a list of vectors, we need the first one [0])
        vector_result = GEMINI_CLIENT.generate_embedding([text_to_embed])[0]

    final_record = {
        "npi": int(doctor['npi']),
        "first_name": doctor['first_name'],
        "last_name": doctor['last_name'],
        "primary_specialty": specialty,
        "bio": extracted_dict.get('bio_text_consolidated', text_to_embed),
        "years_experience": extracted_dict.get('years_experience'),
        "testimonial_summary_text":
        extracted_dict.get('testimonial_summary_text'),
        "profile_picture_url":
        'https://storage.googleapis.com/smarterdoc-profile-media-bucket/headshots/12345.png',
        "latitude": extracted_dict.get('latitude'),
        "longitude": extracted_dict.get('longitude'),
        "education": extracted_dict.get('education', []),
        "hospitals": extracted_dict.get('hospitals', []),
        "ratings": extracted_dict.get('ratings_summary', []),
        "publications": extracted_dict.get('publications', []),
        "certifications": extracted_dict.get('certifications', []),
        # Vector and Timestamp
        "bio_vector": vector_result,
        "updated_at": datetime.datetime.now().isoformat()
    }

    return final_record


async def transform_all_doctors(
        doctors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Runs the enrichment process concurrently for all doctors."""

    tasks = [enrich_single_doctor(d, use_custom_search=False) for d in doctors]

    # asyncio.gather runs all enrichment tasks concurrently
    return await asyncio.gather(*tasks)


# load


def load_data_to_bq(enriched_data: List[Dict[str, Any]],
                    *,
                    batch_size: int = 50,
                    max_retries: int = 4):
    """
    Writes data to BigQuery in small batches with retries.
    Uses load_table_from_json (LOAD job) instead of insert_rows_json (streaming),
    which is more reliable and has server-side retries.
    """
    table_id = f"{settings.GCP_PROJECT_ID}.{settings.BQ_CURATED_DATASET}.{settings.BQ_PROFILES_TABLE}"
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_APPEND")

    total = len(enriched_data)
    print(
        f"-> Starting BigQuery load: {total} rows into {table_id} (batch={batch_size})"
    )

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch = enriched_data[start:end]

        # retry with exponential backoff (2^k seconds)
        attempt = 0
        while True:
            try:
                job = BQ_CLIENT.load_table_from_json(batch,
                                                     table_id,
                                                     job_config=job_config)
                job.result()  # wait for completion
                print(f"   ✓ Loaded rows {start}-{end-1}")
                break
            except Exception as e:
                attempt += 1
                if attempt > max_retries:
                    raise RuntimeError(
                        f"BigQuery load failed for rows {start}-{end-1} after {max_retries} retries: {e}"
                    ) from e
                sleep_s = 2**attempt
                print(
                    f" BQ load error on rows {start}-{end-1}: {e} -> retrying in {sleep_s}s"
                )
                time.sleep(sleep_s)

    print(f"-> Successfully loaded {total} records into BigQuery.")


def run_indexer_job():
    """Main function to run the entire ETL indexer process."""
    print("######### Starting Cloud Run Indexer ETL Job ##########")
    TEST_LIMIT = 200
    # Extract data from BQ
    raw_doctors = get_doctors_for_enrichment(limit=TEST_LIMIT)
    total_extracted = len(raw_doctors)

    if not raw_doctors:
        print("No raw data found or query failed. Exiting.")
        return

    enriched_doctors = asyncio.run(transform_all_doctors(raw_doctors))

    successful_doctors = []
    unprocessed_docs = []
    successful_npis = []
    unprocessed_npis = []
    for d in enriched_doctors:
        if 'failed' not in d:
            successful_doctors.append(d)
            successful_npis.append(d['npi'])
        else:
            unprocessed_docs.append(d)
            unprocessed_npis.append(d['npi'])

    successful_count = len(successful_doctors)
    failed_count = total_extracted - successful_count

    if not successful_doctors:
        print("Enrichment failed for all doctors. Exiting.")
        return

    print("\n--- FINAL JOB SUMMARY ---")
    print(f"Total Records Extracted: {total_extracted}")
    print(f"Records Successfully Enriched: {successful_count}")
    print(f"Records Failed/Skipped: {failed_count}======")
    print(f"Processed NPIs: {successful_npis}=======")
    print(f"Unprocessed doctors: {unprocessed_docs}=======")
    print(f"Unprocessed NPIs: {unprocessed_npis}======")
    print("@@@@@@@@@@@@ Indexer Job Completed Successfully @@@@@@@@@@")

    payload_path = save_payload_jsonl(successful_doctors)

    try:
        load_data_to_bq(successful_doctors, batch_size=50, max_retries=4)
    except Exception as e:
        print(
            f"FATAL: BigQuery load ultimately failed. You can resume upload from file:\n  python -m jobs.resume_upload '{payload_path}'"
        )
        print(f"Error: {e}")
        return


if __name__ == "__main__":
    run_indexer_job()
