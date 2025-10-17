import time
import typing as t
from app.config import settings
from app.util.logging import logger
from app.services.gemini_client import GeminiClient
from app.services.bq_doctor_service import BQDoctorService
from google.cloud import bigquery
from sklearn.feature_extraction.text import TfidfVectorizer

# --- Configuration ---
# For dense embedding on the composite text, embedding dimension must match the model (e.g., 768 for text-embedding-004, 3072 for gemini-embedding-001)
EMBEDDING_MODEL_DIMENSION = 3072
BATCH_SIZE = 50

gemini_client = GeminiClient()
bq_client = bigquery.Client()
bq_service = BQDoctorService(bq_client)
DENSE_VECTOR_TYPE = "FLOAT64"  # Type of the elements
DENSE_VECTOR_MODE = "REPEATED"  # Mode for the array
SPARSE_VECTOR_TYPE = "STRUCT<dimensions ARRAY<INT64>, values ARRAY<FLOAT64>>"
SPARSE_VECTOR_BQ_MODE = None

SPECIALTY_TEXTS_FOR_FIT = [
    "Family Medicine, Sports Medicine",
    "Nurse Anesthetist, Certified Registered", "Obstetrics & Gynecology",
    "Obstetrics & Gynecology, Gynecology",
    "Obstetrics & Gynecology, Reproductive Endocrinology",
    "Orthopaedic Surgery",
    "Orthopaedic Surgery, Adult Reconstructive Orthopaedic Surgery",
    "Orthopaedic Surgery, Foot and Ankle Surgery",
    "Orthopaedic Surgery, Hand Surgery",
    "Orthopaedic Surgery, Orthopaedic Surgery of the Spine",
    "Orthopaedic Surgery, Orthopaedic Trauma",
    "Orthopaedic Surgery, Pediatric Orthopaedic Surgery",
    "Orthopaedic Surgery, Sports Medicine",
    "Registered Nurse, Reproductive Endocrinology/Infertility",
    "Student in an Organized Health Care Education/Training Program"
]


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


vectorizer = TfidfVectorizer(lowercase=True,
                             stop_words='english',
                             token_pattern=r'(?u)\b[A-Za-z]+\b')


def setup_vectorizer():
    """
    Fits the global TfidfVectorizer using the current specialty list.
    """
    logger.info(
        "Starting TF-IDF Vectorizer setup (fitting vocabulary) using current list..."
    )

    if not SPECIALTY_TEXTS_FOR_FIT:
        logger.warning(
            "The specialty list for TF-IDF fitting is empty. Aborting fit.")
        return

    # Fit the vectorizer to build the vocabulary and IDF weights
    vectorizer.fit(SPECIALTY_TEXTS_FOR_FIT)
    logger.info(
        f"TF-IDF Vectorizer successfully fit with a vocabulary size of {len(vectorizer.vocabulary_)}."
    )


def get_sparse_embedding(text: str) -> t.Dict[str, t.Any]:
    """Generates a sparse vector using TF-IDF for specific fields like primary specialty."""
    if not text:
        return {"dimensions": [], "values": []}

    # 1. Transform the text to a sparse matrix (e.g., using TfidfVectorizer)
    vector = vectorizer.transform([text])[0]

    # 2. Convert to the Vertex AI Vector Search sparse embedding format
    # which expects 'dimensions' (token IDs) and 'values' (weights)
    coo_matrix = vector.tocoo()

    return {
        "dimensions": [int(i) for i in coo_matrix.col
                       ],  # Col is the feature index (token ID)
        "values":
        [float(v) for v in coo_matrix.data]  # Data is the TF-IDF weight
    }


def run_re_indexing(attribute: str, is_composite=False):
    """
    Main job function to fetch doctor data, generate new embeddings for specified attribute, 
    and upsert them to BigQuery.
    """
    logger.info(
        f"Starting vector re-indexing job. Composite mode: {is_composite}")
    # Store profiles for upsert after embedding
    profiles_to_process: t.List[t.Dict[str, t.Any]] = []
    # Store the text to send to the embedding API
    texts_to_send: t.List[str] = []

    total_processed = 0

    # Iterate through the generator from BQDoctorService
    for doctor_profile in bq_service.fetch_doctors_for_indexing():

        profiles_to_process.append(doctor_profile)

        if is_composite:
            # ONLY for dense (composite) embedding generation
            texts_to_send.append(build_composite_text(doctor_profile))

        if len(profiles_to_process) >= BATCH_SIZE:

            records_to_upsert = []

            if is_composite:
                # 1. DENSE EMBEDDING PATH
                logger.info("Generating DENSE vectors...")
                new_vectors = gemini_client.generate_embedding(texts_to_send)

                for i, vector in enumerate(new_vectors):
                    # Upsert only the dense vector using the specified attribute name
                    records_to_upsert.append({
                        "npi":
                        profiles_to_process[i]["npi"],
                        attribute:
                        vector if vector else [0.0] *
                        EMBEDDING_MODEL_DIMENSION,
                        "updated_at":
                        time.time(),
                    })
                bq_service.upsert_vectors(records_to_upsert,
                                          attribute,
                                          type=DENSE_VECTOR_TYPE,
                                          mode=DENSE_VECTOR_MODE)

            else:
                # 2. SPARSE EMBEDDING PATH (uses TFIDF)
                logger.info("Generating SPARSE vectors...")
                for profile in profiles_to_process:
                    specialty_text = profile.get('primary_specialty', '')
                    sparse_vector = get_sparse_embedding(specialty_text)

                    # Upsert only the sparse vector using the specified attribute name
                    # NOTE: 'attribute' should be the name of your BigQuery sparse vector column (e.g., 'specialty_sparse_vector')
                    records_to_upsert.append({
                        "npi": profile["npi"],
                        attribute:
                        sparse_vector,  # Sparse vector is the value for the attribute
                        "updated_at": time.time(),
                    })

                bq_service.upsert_vectors(
                    records_to_upsert,
                    attribute,
                    type=
                    "STRUCT",  # Pass type as STRUCT, or the full SPARSE_VECTOR_BQ_TYPE. 
                    # We use STRUCT here as the logic in bq_doctor_service handles the full schema string in the LoadJobConfig.
                    mode="REPEATED"  # Mode for the internal array fields.
                )

        # Process any remaining items in the last batch
        if profiles_to_process:
            records_to_upsert = []
            if is_composite:
                # 1. DENSE EMBEDDING PATH (Final Batch)
                logger.info("Generating DENSE vectors for final batch...")
                new_vectors = gemini_client.generate_embedding(texts_to_send)
                records_to_upsert = [{
                    "npi": profiles_to_process[i]["npi"],
                    attribute:
                    vector if vector else [0.0] * EMBEDDING_MODEL_DIMENSION,
                    "updated_at": time.time()
                } for i, vector in enumerate(new_vectors)]

                bq_service.upsert_vectors(records_to_upsert,
                                          attribute=attribute,
                                          type=DENSE_VECTOR_TYPE,
                                          mode=DENSE_VECTOR_MODE)

            else:
                # 2. SPARSE EMBEDDING PATH (Final Batch)
                logger.info("Generating SPARSE vectors for final batch...")
                for profile in profiles_to_process:
                    specialty_text = profile.get('primary_specialty', '')
                    sparse_vector = get_sparse_embedding(specialty_text)

                    records_to_upsert.append({
                        "npi": profile["npi"],
                        attribute: sparse_vector,
                        "updated_at": time.time(),
                    })

                bq_service.upsert_vectors(records_to_upsert,
                                          attribute=attribute,
                                          type="STRUCT",
                                          mode="REPEATED")

            total_processed += len(
                records_to_upsert
            )  # Now correctly processed after the conditional upsert
            profiles_to_process = []  # Reset after final upsert
            texts_to_send = []  # Reset after final upsert

    logger.info(
        f"Re-indexing job complete. Total doctors processed: {total_processed}"
    )


if __name__ == "__main__":
    setup_vectorizer()
    run_re_indexing("bio_vector", True)
