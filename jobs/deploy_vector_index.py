from google.cloud import aiplatform
from app.config import settings

# --- Configuration ---
# NOTE: These values must be consistent with your BigQuery/Gemini setup
PROJECT_ID = settings.GCP_PROJECT_ID  # <-- Replace with your project ID
REGION = "us-central1"  # <-- Replace with your region
BUCKET_URI = "gs://smartdoc_vectors/"  # <-- GCS location of your JSONL files

INDEX_DISPLAY_NAME = "doctor_embedding_profile_index"
DEPLOYED_INDEX_ID = "doctor_embedding_deployed"  # Must be unique and contain only letters, numbers, or underscores
VECTOR_DIMENSIONS = 3072  # Must match your text-embedding-004 dimensions
APPROXIMATE_NEIGHBORS = 100  # Tuning parameter

# --- Initialize ---
aiplatform.init(project=PROJECT_ID, location=REGION)


# -------------------------------------------------------------------
# A. CREATE THE INDEX ENDPOINT (The server instance)
# -------------------------------------------------------------------
def create_index_endpoint():
    """Creates the Index Endpoint (the server) for querying."""
    print(f"Creating Index Endpoint...")

    # Create the Index Endpoint
    endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
        display_name=f"{INDEX_DISPLAY_NAME}-endpoint",
        public_endpoint_enabled=
        True,  # Allows access via public internet (standard API)
        # For production/security, consider using a private endpoint with VPC peering
    )
    print(f"Index Endpoint created: {endpoint.name}")
    return endpoint


def create_index():
    index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
        display_name=INDEX_DISPLAY_NAME,
        contents_delta_uri=BUCKET_URI,
        dimensions=VECTOR_DIMENSIONS,  # The key change: specify 3072
        approximate_neighbors_count=APPROXIMATE_NEIGHBORS,
        distance_measure_type=
        "COSINE_DISTANCE",  # or DOT_PRODUCT_DISTANCE, based on your vectors
        # Sparse configuration (like embedding_config.sparse_embedding_config) MUST be omitted.
    )
    print(f"Index creation started. Resource name: {index.name}")

    return index


# # -------------------------------------------------------------------
# # B. CREATE THE HYBRID INDEX (Reading vectors from GCS)
# # -------------------------------------------------------------------
# def create_hybrid_index():
#     """Builds the Vector Search Index from data in GCS."""
#     print(
#         f"Creating Index (this may take up to an hour for large datasets)...")

#     # The create_tree_ah_index function reads the JSONL files from the GCS URI
#     index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
#         display_name=INDEX_DISPLAY_NAME,
#         contents_delta_uri=BUCKET_URI,  # Source of your vector data files
#         dimensions=VECTOR_DIMENSIONS,
#         approximate_neighbors_count=APPROXIMATE_NEIGHBORS,
#         distance_measure_type=
#         "DOT_PRODUCT_DISTANCE",  # Common for semantic search
#         # We must use STREAM_UPDATE to support the Sparse Vector format
#         # and be able to update with the streaming MatchEngineIndex.
#         index_update_method="STREAM_UPDATE",
#     )
#     print(f"Index creation started. Resource name: {index.name}")
#     return index


# -------------------------------------------------------------------
# C. DEPLOY THE INDEX TO THE ENDPOINT (Goes live)
# -------------------------------------------------------------------
def deploy_index(index: aiplatform.MatchingEngineIndex,
                 endpoint: aiplatform.MatchingEngineIndexEndpoint):
    """Deploys the created Index to the Index Endpoint."""
    print(f"Deploying Index to Endpoint (this may take ~20 minutes)...")

    deployed_endpoint = endpoint.deploy_index(
        index=index,
        deployed_index_id=DEPLOYED_INDEX_ID,
        # Set machine type and replicas based on expected load/budget
        machine_type='e2-standard-16',
        min_replica_count=1,
        max_replica_count=2,
    )
    print(
        f"Index successfully deployed. Deployed Index ID: {DEPLOYED_INDEX_ID}")
    return deployed_endpoint


# -------------------------------------------------------------------
# MAIN EXECUTION
# -------------------------------------------------------------------
if __name__ == "__main__":
    # Ensure environment is set up (IAM roles, APIs enabled)

    try:
        # Step 1: Create the live server endpoint
        index_endpoint = create_index_endpoint()

        # Step 2: Build the index from the data you exported to GCS
        # Note: Index creation is a Long Running Operation (LRO) and can take time
        matching_index = create_index()

        # Step 3: Deploy the index to the endpoint
        deploy_index(matching_index, index_endpoint)

        print("\n✅ Deployment Complete! Your Hybrid Search Index is now live.")
        print(
            f"   Use the following in your settings.py for VertexVectorSearchService:"
        )
        print(f"   VECTOR_SEARCH_ENDPOINT_NAME = '{index_endpoint.name}'")
        print(f"   VECTOR_SEARCH_DEPLOYED_INDEX_ID = '{DEPLOYED_INDEX_ID}'")

    except Exception as e:
        print(f"\n❌ An error occurred during indexing or deployment: {e}")
