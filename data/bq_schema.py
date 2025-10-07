import os
from google.cloud import bigquery
from typing import List

PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
RAW_DATASET = "gcs_npi_staging"
CURATED_DATASET = "curated"


def create_bq_client():
    """Initializes and returns the BigQuery client."""
    return bigquery.Client(project=PROJECT_ID)


def create_dataset_if_not_exists(client: bigquery.Client, dataset_id: str):
    """Creates a BigQuery dataset if it doesn't already exist."""
    dataset_ref = client.dataset(dataset_id)
    try:
        client.get_dataset(dataset_ref)
    except Exception:
        print(f"Dataset {dataset_id} not found. Creating it...")
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        client.create_dataset(dataset)
        print(f"Dataset {dataset_id} created.")


def get_curated_profiles_schema() -> List[bigquery.SchemaField]:
    """
    Defines the final schema for the enriched doctor profile table.
    This schema is a combination of key NPI fields and the custom enriched fields.
    """
    return [
        # Key fields extracted from the raw NPI JSON
        bigquery.SchemaField("npi",
                             "INT64",
                             mode="REQUIRED",
                             description="NPI Number (Primary Key)"),
        bigquery.SchemaField("first_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("last_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("primary_specialty",
                             "STRING",
                             mode="NULLABLE",
                             description="Primary taxonomy description"),
        bigquery.SchemaField("city",
                             "STRING",
                             mode="NULLABLE",
                             description="Primary location city"),

        # Custom Enriched Fields
        bigquery.SchemaField(
            "bio",
            "STRING",
            mode="NULLABLE",
            description="Detailed biography from search results"),
        bigquery.SchemaField(
            "profile_url",
            "STRING",
            mode="NULLABLE",
            description="Best profile link found via Google Search"),
        bigquery.SchemaField("years_experience",
                             "INT64",
                             mode="NULLABLE",
                             description="Experience extracted by LLM/logic"),
        bigquery.SchemaField("testimonials",
                             "STRING",
                             mode="REPEATED",
                             description="Summarized patient testimonials"),
        bigquery.SchemaField("publications",
                             "STRING",
                             mode="REPEATED",
                             description="Research and publications"),
        bigquery.SchemaField(
            "profile_picture_url",
            "STRING",
            mode="NULLABLE",
            description="URL for the doctor's profile image found via search"),
        bigquery.SchemaField(
            "ratings",
            "RECORD",
            mode="REPEATED",
            description="Reviews and ratings from various sources"),
        # 3. Vector and Metadata Fields
        bigquery.SchemaField(
            "bio_vector",
            "FLOAT64",
            mode="REPEATED",
            description="Vertex AI embedding vector (ARRAY<FLOAT64>)"),
        bigquery.SchemaField(
            "updated_at",
            "TIMESTAMP",
            mode="REQUIRED",
            description="Timestamp of the last enrichment/indexing"),
    ]


def create_curated_tables():
    """Main function to create all necessary tables in the curated dataset."""
    client = create_bq_client()
    create_dataset_if_not_exists(client, CURATED_DATASET)

    # 1. Create the final enriched doctor profile table
    table_id = f"{PROJECT_ID}.{CURATED_DATASET}.doctor_profiles"
    schema = get_curated_profiles_schema()

    table = bigquery.Table(table_id, schema=schema)
    table.time_partitioning = bigquery.TimePartitioning(
        field="updated_at"  # Partition by the update time for cost efficiency
    )

    try:
        client.create_table(table)
        print(f"Table {table_id} created successfully.")
    except Exception as e:
        # If the table already exists, BigQuery throws an exception, which is fine.
        if "Already Exists" in str(e):
            print(f"Table {table_id} already exists.")
        else:
            print(f"Error creating table {table_id}: {e}")


if __name__ == "__main__":
    create_curated_tables()
