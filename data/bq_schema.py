import os
from google.cloud import bigquery
from google.cloud.bigquery import SchemaField
from typing import List, Optional
from app.config import settings
from app.deps import get_bq_sync

PROJECT_ID = settings.GCP_PROJECT_ID
CURATED_DATASET = settings.BQ_CURATED_DATASET
PROFILES_TABLE = settings.BQ_PROFILES_TABLE


def get_bq_client(client: Optional[bigquery.Client] = None) -> bigquery.Client:
    """Gets global bq client."""
    return client or get_bq_sync()


def create_dataset_if_not_exists(client: Optional[bigquery.Client],
                                 dataset_id: str):
    """Creates a BigQuery dataset if it doesn't exist."""
    client = get_bq_client(client)
    dataset_ref = client.dataset(dataset_id)
    try:
        client.get_dataset(dataset_ref)
        print(f"Dataset {dataset_id} already exists.")
    except Exception:
        print(f"Dataset {dataset_id} not found. Creating it...")
        dataset = bigquery.Dataset(dataset_ref)
        # Use the region from settings
        dataset.location = settings.GCP_REGION
        client.create_dataset(dataset)
        print(f"Dataset {dataset_id} created.")


def get_profiles_schema() -> List[SchemaField]:
    """Defines the schema for the curated doctor profiles table."""
    return [
        # Keys and Core NPI data
        SchemaField("npi",
                    "INTEGER",
                    mode="REQUIRED",
                    description="Unique NPI identifier"),
        SchemaField("first_name", "STRING"),
        SchemaField("last_name", "STRING"),
        SchemaField("primary_specialty", "STRING"),
        SchemaField("bio",
                    "STRING",
                    description="Comprehensive consolidated biography."),
        SchemaField("profile_picture_url",
                    "STRING",
                    description="Public URL for doctor's portrait."),
        SchemaField("years_experience",
                    "INTEGER",
                    description="Calculated years of clinical experience."),
        SchemaField("testimonial_summary_text",
                    "STRING",
                    description="LLM summary of patient feedback."),
        SchemaField("publications",
                    "STRING",
                    mode="REPEATED",
                    description="Titles of key research papers."),
        SchemaField(
            "education",
            "STRING",
            mode="REPEATED",
            description="List of medical school(s)/residency attended."),
        SchemaField("hospitals",
                    "STRING",
                    mode="REPEATED",
                    description="List of hospitals/clinics affiliated with."),
        SchemaField(
            "certifications",
            "STRING",
            mode="REPEATED",
            description="List of board certifications the doctor holds."),
        SchemaField(
            "latitude",
            "FLOAT64",
            description=
            "Decimal latitude coordinate of the primary practice location."),
        SchemaField(
            "longitude",
            "FLOAT64",
            description=
            "Decimal longitude coordinate of the primary practice location."),
        SchemaField("address",
                    "STRING",
                    description="Formatted practice address."),
        # Array of Records for Ratings (to preserve source granularity)
        SchemaField(
            "ratings",
            "RECORD",
            mode="REPEATED",
            description="List of structured ratings from external platforms.",
            fields=[
                SchemaField("source", "STRING"),
                SchemaField("score", "FLOAT64"),
                SchemaField("count", "INTEGER"),
                SchemaField("link", "STRING"),
            ]),
        SchemaField(
            "bio_vector",
            "FLOAT64",
            mode="REPEATED",
            description="768-dimension text embedding for RAG/Similarity."),
        SchemaField("updated_at",
                    "TIMESTAMP",
                    description="Last enrichment date.")
    ]


def create_doctor_profiles_table(client: Optional[bigquery.Client]):
    """
    Creates the curated.doctor_profiles table OR performs schema evolution 
    (ALTER TABLE) if the table already exists.
    """
    client = get_bq_client()
    table_id = f"{PROJECT_ID}.{CURATED_DATASET}.{PROFILES_TABLE}"
    target_schema = get_profiles_schema()

    table = bigquery.Table(table_id, schema=target_schema)

    table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field="updated_at",
        expiration_ms=None)

    try:
        # Try to create the table (if it's brand new)
        client.create_table(table)
        print(f"Table {table_id} created successfully.")

    except Exception as e:
        if "Already Exists" in str(e):
            print(
                f"Table {table_id} already exists. Checking for schema updates..."
            )

            # The table exists, now check for schema evolution
            current_table = client.get_table(table_id)
            current_field_names = {f.name for f in current_table.schema}

            columns_to_add = []
            for target_field in target_schema:
                if target_field.name not in current_field_names:
                    columns_to_add.append(target_field)

            if columns_to_add:
                alter_statements = []
                for field in columns_to_add:
                    if field.mode == 'REPEATED' and field.field_type != "RECORD":
                        type_def = f"ARRAY<{field.field_type}>"
                    elif field.mode == 'REQUIRED':
                        type_def = f"{field.field_type} NOT NULL"
                    # to add nested records would need to write STRUCT DDL (not needed right now)
                    elif field.field_type == "RECORD":
                        raise RuntimeError(
                            f"Nested field '{field.name}' cannot be auto-added by this helper."
                        )
                    else:
                        type_def = field.field_type

                    desc = field.description or ""
                    alter_statements.append(
                        f"ADD COLUMN {field.name} {type_def} OPTIONS(description='{desc}')"
                    )

                full_alter_query = f"ALTER TABLE `{table_id}` {', '.join(alter_statements)}"
                client.query(full_alter_query).result()
                print(
                    f"Successfully ran ALTER TABLE to add {len(columns_to_add)} column(s)."
                )
            else:
                print("Schema is up to date. No columns added.")

        else:
            print(f"FATAL Error creating or updating table {table_id}: {e}")


def create_curated_tables():
    """Orchestrates the creation of all final BigQuery tables."""
    client = get_bq_client()

    # curated dataset
    create_dataset_if_not_exists(client, CURATED_DATASET)

    # main doctor profiles table
    create_doctor_profiles_table(client)

    print("\nBigQuery Schema Setup Complete.")


if __name__ == "__main__":
    if 'PYTHONPATH' not in os.environ or '.' not in os.environ['PYTHONPATH']:
        os.environ['PYTHONPATH'] = os.environ.get('PYTHONPATH', '') + (
            ':' if os.environ.get('PYTHONPATH') else '') + '.'

    create_curated_tables()
