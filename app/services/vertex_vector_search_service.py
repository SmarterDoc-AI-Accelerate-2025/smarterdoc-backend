import asyncio
from typing import List, Dict, Any, TYPE_CHECKING, Optional

from google.cloud import aiplatform
from google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint import (
    HybridQuery,
    MatchingEngineIndexEndpoint,
    MatchNeighbor,
)

from app.config import settings
from app.util.logging import logger

from app.services.bq_doctor_service import BQDoctorService


class VertexVectorSearchService:
    """
    Handles all interactions with Vertex AI Vector Search (Matching Engine) 
    for low-latency retrieval.
    """

    def __init__(self, bq_service: 'BQDoctorService'):
        """
        Initializes the connection to the deployed Vector Search index endpoint.
        
        Args:
            bq_service: An instance of your BQDoctorService to fetch full profiles 
                        after a vector match.
        """
        self.bq_service = bq_service

        # 1. Initialize Vertex AI client
        # Force gRPC transport to avoid REST query param issues on public endpoints
        aiplatform.init(project=settings.GCP_PROJECT_ID,
                        location=settings.GCP_REGION,
                        api_transport="grpc")

        # 2. Instantiate the deployed Index Endpoint
        # These names must match your deployment in Google Cloud Console/Vertex AI
        self.deployed_index_id = settings.VECTOR_SEARCH_DEPLOYED_INDEX_ID

        # MatchingEngineIndexEndpoint connects to the live service endpoint
        self.endpoint: MatchingEngineIndexEndpoint = MatchingEngineIndexEndpoint(
            index_endpoint_name=settings.VECTOR_SEARCH_ENDPOINT_NAME)
        logger.info(
            f"Initialized Vector Search Endpoint: {settings.VECTOR_SEARCH_ENDPOINT_NAME}"
        )


# -------------------------------------------------------------------
# THE HYBRID SEARCH FUNCTION
# -------------------------------------------------------------------

    async def search_hybrid(
        self,
        dense_vector: List[float],
        sparse_vector_data: Dict[List[str], List[float]],
        k: int,
        rrf_alpha: float,
        metadata_filters: Optional[Dict[str,
                                        Any]] = None) -> List[Dict[str, Any]]:
        """
        Performs a hybrid search (Dense + Sparse + RRF) against the deployed index.

        The process is:
        1. Query the Vector Search Endpoint with both vectors.
        2. Get the top K matching IDs (NPIs) and their RRF scores.
        3. Look up the full doctor profiles in BigQuery/DB using the NPIs (Data Enrichment).
        4. Return the enriched profiles with the RRF score attached.
        """
        logger.info(f"===== DEBUG SHOW DENSE VECTORS: {dense_vector[:4]} ")
        sparse_dims = sparse_vector_data.get("dimensions", [])
        sparse_values = sparse_vector_data.get("values", [])
        logger.info(
            "DEBUG: SPARSE VECTORS: Dimensions Length=%d, Values Length=%d",
            len(sparse_dims), len(sparse_values))

        if sparse_dims and sparse_values:
            logger.info("DEBUG: SPARSE DIMS ELEMENT TYPE: %s",
                        type(sparse_dims[0]))
        try:
            safe_sparse_dims = [int(d)
                                for d in sparse_dims] if sparse_dims else []
            # 1. Create the HybridQuery object
            query = HybridQuery(
                dense_embedding=dense_vector,
                # sparse_embedding_values=sparse_vector_data["values"],
                # sparse_embedding_dimensions=sparse_vector_data["dimensions"],
                sparse_embedding_values=sparse_values,
                sparse_embedding_dimensions=safe_sparse_dims,
                rrf_ranking_alpha=rrf_alpha)
        except Exception as e:
            logger.error(f"Error constructing HybridQuery: {e}")
            return []

        def _find_neighbors_sync(deployed_id, query_list, num, filters):
            """Synchronous function to be run in the executor."""
            return self.endpoint.find_neighbors(deployed_index_id=deployed_id,
                                                queries=query_list,
                                                num_neighbors=num,
                                                filter=filters)

        # 2. Execute the query using the endpoint's find_neighbors method
        try:
            loop = asyncio.get_event_loop()

            # find_neighbors is synchronous and must be run in an executor in an async function
            results: List[List[MatchNeighbor]] = await loop.run_in_executor(
                None,  # Executor
                _find_neighbors_sync,  # Function to run
                self.deployed_index_id,  # Arg 1: deployed_id (Positional)
                [query],  # Arg 2: query_list (Positional)
                k,  # Arg 3: num (Positional)
                metadata_filters  # Arg 4: filters (Positional)
            )

            # 3. Process results: Extract NPIs and RRF Scores
            matched_npi_data = {}
            if results and results[0]:
                for match_neighbor in results[0]:
                    npi = match_neighbor.id
                    # The 'distance' attribute on MatchNeighbor contains the RRF score
                    matched_npi_data[npi] = {
                        "npi": npi,
                        "semantic_similarity_score": match_neighbor.distance,
                    }

            if not matched_npi_data:
                logger.warning("Hybrid search returned no matches.")
                return []

            # 4. CRITICAL LOOK-UP STEP: Fetch full doctor profiles from BQ/DB
            npi_list = list(matched_npi_data.keys())

            # Use the injected BQ service instance
            # NOTE: This method on your BQDoctorService must be implemented to fetch full data by NPI list.
            full_profiles = await self.bq_service.fetch_full_profiles_by_npi(
                npi_list)

            # 5. Combine scores and profiles (Data Enrichment)
            candidates = []
            for profile in full_profiles:
                npi = profile.get('npi')
                if npi in matched_npi_data:
                    # Merge the full profile data with the RRF score obtained from Vector Search
                    profile_with_score = {
                        **profile, "semantic_similarity_score":
                        matched_npi_data[npi]["semantic_similarity_score"]
                    }
                    candidates.append(profile_with_score)

            logger.info(
                f"Successfully enriched {len(candidates)} candidates from DB lookup."
            )
            return candidates

        except Exception as e:
            logger.error(f"Hybrid Search execution failed. Error: {e}")
            return []

    async def search_dense(
        self,
        dense_vector: List[float],
        k: int,
        metadata_filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Performs a dense embedding search against the deployed index.

        The process is:
        1. Query the Vector Search Endpoint with dense vector only.
        2. Get the top K matching IDs (NPIs) and their similarity scores.
        3. Look up the full doctor profiles in BigQuery/DB using the NPIs (Data Enrichment).
        4. Return the enriched profiles with the similarity score attached.
        """
        logger.info(f"===== DEBUG SHOW DENSE VECTORS: {dense_vector[:4]} ")

        try:
            # 1. For dense-only search, we can pass the dense vector directly
            # According to the API documentation, queries can be List[List[float]] for dense-only queries
            pass  # We'll pass the dense_vector directly to find_neighbors
        except Exception as e:
            logger.error(f"Error preparing dense query: {e}")
            return []

        def _find_neighbors_sync(deployed_id, query_list, num, filters):
            """Synchronous function to be run in the executor."""
            return self.endpoint.find_neighbors(deployed_index_id=deployed_id,
                                                queries=query_list,
                                                num_neighbors=num,
                                                filter=filters)

        # 2. Execute the query using the endpoint's find_neighbors method
        try:
            loop = asyncio.get_event_loop()

            # find_neighbors is synchronous and must be run in an executor in an async function
            # For dense-only search, we pass the dense vector directly as List[List[float]]
            results: List[List[MatchNeighbor]] = await loop.run_in_executor(
                None,  # Executor
                _find_neighbors_sync,  # Function to run
                self.deployed_index_id,  # Arg 1: deployed_id (Positional)
                [dense_vector],  # Arg 2: query_list (Positional) - pass dense vector directly
                k,  # Arg 3: num (Positional)
                metadata_filters  # Arg 4: filters (Positional)
            )

            # 3. Process results: Extract NPIs and Similarity Scores
            matched_npi_data = {}
            if results and results[0]:
                for match_neighbor in results[0]:
                    npi = match_neighbor.id
                    # The 'distance' attribute on MatchNeighbor contains the similarity score
                    matched_npi_data[npi] = {
                        "npi": npi,
                        "semantic_similarity_score": match_neighbor.distance,
                    }

            if not matched_npi_data:
                logger.warning("Dense search returned no matches.")
                return []

            # 4. CRITICAL LOOK-UP STEP: Fetch full doctor profiles from BQ/DB
            npi_list = list(matched_npi_data.keys())

            # Use the injected BQ service instance
            # NOTE: This method on your BQDoctorService must be implemented to fetch full data by NPI list.
            full_profiles = await self.bq_service.fetch_full_profiles_by_npi(
                npi_list)

            # 5. Combine scores and profiles (Data Enrichment)
            candidates = []
            for profile in full_profiles:
                npi = profile.get('npi')
                if npi in matched_npi_data:
                    # Merge the full profile data with the similarity score obtained from Vector Search
                    profile_with_score = {
                        **profile, "semantic_similarity_score":
                        matched_npi_data[npi]["semantic_similarity_score"]
                    }
                    candidates.append(profile_with_score)

            logger.info(
                f"Successfully enriched {len(candidates)} candidates from DB lookup."
            )
            return candidates

        except Exception as e:
            logger.error(f"Dense Search execution failed. Error: {e}")
            return []

    async def diagnostics_read_index_datapoints(self, ids: List[str]) -> List[Dict[str, Any]]:
        """
        Diagnostic helper to verify whether specific IDs exist in the deployed index
        and to inspect basic vector info for those datapoints.
        """
        if not ids:
            return []

        def _read_sync(deployed_id: str, id_list: List[str]):
            return self.endpoint.read_index_datapoints(
                deployed_index_id=deployed_id,
                ids=id_list,
            )

        try:
            loop = asyncio.get_event_loop()
            datapoints = await loop.run_in_executor(
                None,
                _read_sync,
                self.deployed_index_id,
                ids,
            )

            results = []
            for dp in datapoints:
                try:
                    dp_id = getattr(dp, "datapoint_id", None) or getattr(dp, "id", None)
                    feature_vector = getattr(dp, "feature_vector", None)
                    results.append({
                        "id": str(dp_id) if dp_id is not None else None,
                        "has_vector": bool(feature_vector),
                        "vector_dim": len(feature_vector) if feature_vector else 0,
                    })
                except Exception:
                    continue
            return results
        except Exception as e:
            logger.error(f"Diagnostics read_index_datapoints failed: {e}")
            return []