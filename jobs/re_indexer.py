import time
import typing as t
from app.config import settings
from app.util.logging import logger
from app.services.gemini_client import GeminiClient
from app.services.bq_doctor_service import BQDoctorService
from google.cloud import bigquery

# --- Configuration ---
# For dense embedding on the composite text, embedding dimension must match the model (e.g., 768 for text-embedding-004, 3072 for gemini-embedding-001)
EMBEDDING_MODEL_DIMENSION = 3072
BATCH_SIZE = 50

gemini_client = GeminiClient()
bq_client = bigquery.Client()
bq_service = BQDoctorService(bq_client)
DENSE_VECTOR_TYPE = "FLOAT64"  # Type of the elements
DENSE_VECTOR_MODE = "REPEATED"  # Mode for the array


def build_composite_text(doc: t.Dict[str, t.Any]) -> str:
    """
    Builds the composite text string by concatenating relevant doctor profile fields.
    This is the input for the embedding model.
    """

    # Helper to safely join list fields or get string fields
    def safe_join(field):
        value = doc.get(field)
        if isinstance(value, list):
            return ', '.join(filter(None, value))
        return str(value) if value else ''

    composite_embed_text = " ".join(
        filter(None, [
            f"SPECIALTY: {safe_join('primary_specialty')}",
            f"BIO: {safe_join('bio')}",
            f"SUMMARY: {safe_join('testimonial_summary_text')}",
            f"PUBS: {safe_join('publications')}",
            f"CERTS: {safe_join('certifications')}",
            f"EDUCATION: {safe_join('education')}",
            f"HOSPITALS: {safe_join('hospitals')}",
        ]))
    return composite_embed_text.strip()


def run_re_indexing(attribute: str):
    """
    Main job function to fetch doctor data (where bio_vector IS NULL), generate new embeddings, 
    and upsert them to BigQuery.
    """
    logger.info(f"Starting vector re-indexing job targeting NULL vectors.")

    profiles_to_process: t.List[t.Dict[str, t.Any]] = []
    texts_to_send: t.List[str] = []
    total_processed = 0

    # Iterate through the generator from BQDoctorService
    # This service method MUST query WHERE bio_vector IS NULL
    for doctor_profile in bq_service.fetch_doctors_for_indexing():

        profiles_to_process.append(doctor_profile)
        texts_to_send.append(build_composite_text(doctor_profile))

        # --- MAIN BATCH PROCESSING BLOCK ---
        if len(profiles_to_process) >= BATCH_SIZE:

            # Use the local variables and immediately reset them for the next batch
            current_profiles = profiles_to_process
            current_texts = texts_to_send

            logger.info(
                f"Generating DENSE vectors for batch size: {len(current_profiles)}"
            )
            new_vectors = gemini_client.generate_embedding(current_texts)

            records_to_upsert = []
            for i, vector in enumerate(new_vectors):
                records_to_upsert.append({
                    "npi":
                    current_profiles[i]["npi"],
                    attribute:
                    vector if vector else [0.0] * EMBEDDING_MODEL_DIMENSION,
                    "updated_at":
                    time.time(),
                })

            bq_service.upsert_vectors(records_to_upsert,
                                      attribute,
                                      type=DENSE_VECTOR_TYPE,
                                      mode=DENSE_VECTOR_MODE)

            total_processed += len(records_to_upsert)

            # Reset lists for the next batch
            profiles_to_process = []
            texts_to_send = []

    # --- PROCESS FINAL REMAINING BATCH ---
    if profiles_to_process:
        logger.info(
            f"Generating DENSE vectors for final batch size: {len(profiles_to_process)}"
        )

        # Use the remaining data
        current_profiles = profiles_to_process
        current_texts = texts_to_send

        new_vectors = gemini_client.generate_embedding(current_texts)

        records_to_upsert = [{
            "npi": current_profiles[i]["npi"],
            attribute: vector if vector else [0.0] * EMBEDDING_MODEL_DIMENSION,
            "updated_at": time.time()
        } for i, vector in enumerate(new_vectors)]

        bq_service.upsert_vectors(records_to_upsert,
                                  attribute=attribute,
                                  type=DENSE_VECTOR_TYPE,
                                  mode=DENSE_VECTOR_MODE)

        total_processed += len(records_to_upsert)

        # Lists are implicitly empty after the loop is done

    logger.info(
        f"Re-indexing job complete. Total doctors processed: {total_processed}"
    )


if __name__ == "__main__":
    run_re_indexing("bio_vector")
