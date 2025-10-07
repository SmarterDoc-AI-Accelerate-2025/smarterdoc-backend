# jobs/indexer.py

import asyncio
import datetime
import json
from typing import List, Dict, Any

from google.cloud import bigquery
from app.config import settings
from app.services.gemini_client import GeminiClient, EnrichedProfileData
from app.services.web_search import web_search_client, WebSearchClient

BQ_CLIENT = bigquery.Client(project=settings.GCP_PROJECT_ID)
GEMINI_CLIENT = GeminiClient()

# ELASTIC_CLIENT = ElasticClient()


# Extraction
def get_doctors_for_enrichment(limit: int = 1000) -> List[Dict[str, Any]]:
    """
    Pulls raw doctor data from the Fivetran-loaded table in BigQuery.
    Extracts structured fields from the raw JSON column for processing.
    """
    raw_table = f"{settings.BQ_RAW_DATASET}.{settings.BQ_RAW_TABLE}"

    # JSON_EXTRACT_SCALAR flattens Fivetran JSON structure
    # this query uses JSON functions to access nested fields in the _data JSON blob.
    query = f"""
    SELECT
        JSON_EXTRACT_SCALAR(_data, '$.number') AS npi,
        JSON_EXTRACT_SCALAR(_data, '$.basic.first_name') AS first_name,
        JSON_EXTRACT_SCALAR(_data, '$.basic.last_name') AS last_name,
        
        -- Extract the primary specialty description where 'primary' is true
        COALESCE(
            (SELECT tax.desc FROM UNNEST(JSON_EXTRACT_ARRAY(_data, '$.taxonomies')) tax_json, 
            UNNEST(JSON_QUERY_ARRAY(tax_json)) AS tax
            WHERE JSON_EXTRACT_SCALAR(tax, '$.primary') = 'true'
            LIMIT 1),
            -- Fallback to the first specialty if no primary is explicitly set
            JSON_EXTRACT_SCALAR(JSON_EXTRACT_ARRAY(_data, '$.taxonomies')[OFFSET(0)], '$.desc')
        ) AS primary_specialty,
        
        -- Pass the entire JSON blob for easier processing if needed later
        _data AS full_npi_json 
    FROM
        `{settings.GCP_PROJECT_ID}.{raw_table}`
    -- Ensure you only query recent data to limit cost/processing in a production setting
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


# Transformation


async def enrich_single_doctor(
        doctor: Dict[str, Any],
        use_custom_search: bool = False) -> Dict[str, Any]:
    """
    Handles the sequential, high-latency enrichment steps for one doctor, 
    switching between LLM Grounding and Custom Search based on flags.
    """

    name = f"{doctor['first_name']} {doctor['last_name']}"
    specialty = doctor.get('primary_specialty', 'Physician')

    # default: use gemini LLM with built-in grounding

    if not use_custom_search:
        prompt = (
            f"""As a medical data expert, find the official profile and review information for 
    Dr. {name}, a specialist in {specialty}. Extract their years of experience, 
    average patient ratings, key publications, and a profile picture URL.
    **Summarize key patient testimonials** to help new patients make informed decisions.
    Use Google Search as your tool. Calculate years of experience from their graduation or residency end date."""
        )
        enriched_data = GEMINI_CLIENT.extract_structured_data_with_grounding(
            prompt_instruction=prompt)

    # fall-back: custom web search with LLM
    else:
        if not isinstance(web_search_client, WebSearchClient):
            print(
                f"Warning: custom search client not initialized correctly. Skipping NPI {doctor['npi']}."
            )
            return {
                **doctor, "updated_at": datetime.datetime.now().isoformat()
            }

        # calls custom client
        raw_bio_text, profile_url, review_snippets = await web_search_client.search_and_extract_bio(
            doctor)

        prompt = (
            f"Analyze the following consolidated web text and extract the structured data. "
            f"Consolidated Text: ---START--- {raw_bio_text} ---END---")
        enriched_data = GEMINI_CLIENT.extract_structured_data(
            unstructured_text=prompt)

        if enriched_data:
            enriched_data['profile_picture_url'] = profile_url

    # error handling/ vectorization

    if not enriched_data:
        print(
            f"Warning: Failed to enrich NPI {doctor['npi']} using {'Grounding' if not use_custom_search else 'Custom Search'}. Returning raw data."
        )
        return {**doctor, "updated_at": datetime.datetime.now().isoformat()}

    # The text used for the vector should be the combined professional bio
    text_to_embed = enriched_data.get(
        'bio_text_consolidated', raw_bio_text if use_custom_search else "")

    # Placeholder: Call Vertex AI Embeddings API (Need to implement this in GeminiClient)
    # vector_result = GEMINI_CLIENT.generate_embedding([text_to_embed])[0]
    vector_result = [0.0] * 768  # Placeholder for 768-dim embedding

    final_record = {
        "npi": int(doctor['npi']),
        "first_name": doctor['first_name'],
        "last_name": doctor['last_name'],
        "primary_specialty": specialty,

        # mapping from EnrichedProfileData schema
        "bio": enriched_data.get('bio_text_consolidated', text_to_embed),
        "profile_picture_url": enriched_data.get('profile_picture_url'),
        "years_experience": enriched_data.get('years_experience'),
        "ratings": enriched_data.get('ratings_summary', []),
        "publications": enriched_data.get('publications', []),
        "bio_vector": vector_result,
        "updated_at": datetime.datetime.now().isoformat()
    }

    return final_record


async def transform_all_doctors(
        doctors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Runs the enrichment process concurrently for all doctors."""
    # Use the Indexer Batch Size from config to manage concurrency
    # since we only have 870, this will run in one or two large batches.

    # NOTE: The default setting (use_custom_search=False) enables LLM Grounding.
    tasks = [enrich_single_doctor(d, use_custom_search=False) for d in doctors]

    # asyncio.gather runs all enrichment tasks concurrently
    return await asyncio.gather(*tasks)


# Load


def load_data(enriched_data: List[Dict[str, Any]]):
    """Writes data to BigQuery and ElasticSearch"""

    # BQ write
    table_id = f"{settings.GCP_PROJECT_ID}.{settings.BQ_CURATED_DATASET}.{settings.BQ_PROFILES_TABLE}"
    try:
        # BQ insert_rows_json expects python dictionaries
        errors = BQ_CLIENT.insert_rows_json(table_id, enriched_data)
        if errors:
            print(f"WARNING: Errors occurred inserting data into BQ: {errors}")
        else:
            print(
                f"-> Successfully loaded {len(enriched_data)} records into BigQuery table {table_id}."
            )
    except Exception as e:
        print(f"FATAL ERROR during BQ Load: {e}")
        return

    # elastic Upsert
    try:
        # ELASTIC_CLIENT.bulk_upsert(enriched_data, index_name=settings.ELASTIC_INDEX_DOCTORS)
        print(
            f"-> Indexed {len(enriched_data)} records into ElasticSearch index {settings.ELASTIC_INDEX_DOCTORS} (Placeholder)."
        )
    except Exception as e:
        print(f"WARNING: Errors occurred during Elastic Upsert: {e}")


def run_indexer_job():
    """Main function to run the entire ETL indexer process."""
    print("######### Starting Cloud Run Indexer ETL Job ##########")

    # Extract data from BQ
    raw_doctors = get_doctors_for_enrichment(limit=870)
    if not raw_doctors:
        print("No raw data found or query failed. Exiting.")
        return

    # Async Transform (Enrichment)
    enriched_doctors = asyncio.run(transform_all_doctors(raw_doctors))

    # Filter out any failed enrichments before loading
    enriched_doctors = [d for d in enriched_doctors if 'npi' in d]

    if not enriched_doctors:
        print("Enrichment failed for all doctors. Exiting.")
        return

    # Load (BQ & Elastic)
    load_data(enriched_doctors)

    print("@@@@@@@@@@@@ Indexer Job Completed Successfully @@@@@@@@@@")


if __name__ == "__main__":
    run_indexer_job()
