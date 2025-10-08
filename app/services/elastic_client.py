from elasticsearch import Elasticsearch
from typing import List, Any, Dict
from app.models.schemas import SearchRequest, DoctorHit, EstimateRequest
from app.util.logging import logger
from app.config import settings

# Dummy implementation
# Placeholder data to return on search
MOCK_CANDIDATE = DoctorHit(
    npi="1234567890",
    name="Dr. Mock Specialist",
    specialties=["Orthopedic Surgery", "Sports Medicine"],
    metro="nyc",
    distance_km=4.2,
    in_network=True,
    reputation_score=0.95,
    factors={
        "Experience": 25.0,
        "Network": 30.0
    },
    citations=["PubMed(2023)", "Hospital Profile"],
    education=[
        "NYU School of Medicine", "Hospital for Special Surgery Residency"
    ],
    hospitals=["NYU Langone", "Mount Sinai"])

# Note: These functions are defined outside the class so they can be imported directly
# by the API (app/api/v1/search.py).


def hybrid_search(req: SearchRequest, es: Any = None) -> list[DoctorHit]:
    """MOCK: Simulates hybrid search, returning mock results."""
    # This is the function that needs to be imported in search.py
    # ... (implementation remains the same as your mock)
    # logger.info(f"MOCK SEARCH: Query received: {req.query}. Returning mock data.")
    return [MOCK_CANDIDATE]  # Simplified placeholder response


def fetch_evidence_ids(es: Any,
                       npi: str,
                       condition_slug: str,
                       limit: int = 3) -> list[str]:
    """MOCK: Simulates fetching related evidence, returns static URLs."""
    logger.info(f"MOCK EVIDENCE: Fetching evidence for NPI {npi}.")
    return [
        "https://pubmed.ncbi.nlm.nih.gov/3001", "https://hospital.org/research"
    ]


class ElasticClient:
    """
    The actual ElasticSearch client class structure (used by the Indexer, 
    but not used by the main API endpoints in this mock setup).
    """

    def __init__(self):
        logger.warning(
            "ElasticClient initialized. This client is currently a MOCK.")
        self.es = None  # Explicitly set to None to prevent accidental use/crash

    def bulk_upsert(self, records: List[Dict[str, Any]],
                    index_name: str) -> int:
        """MOCK: Indexer is running without ElasticSearch."""
        logger.warning(
            f"MOCK: Indexing {len(records)} records into ElasticSearch index '{index_name}' skipped."
        )
        return len(records)


    def fetch_evidence_ids(self,
                           npi: str,
                           condition_slug: str,
                           limit: int = 3) -> list[str]:
        """Placeholder for fetching evidence documents related to a doctor."""
        logger.warning("Fetch evidence is a placeholder.")
        return []

# --- Backward compatibility patch for API import ---
def hybrid_search(es=None, req=None):
    """
    Temporary wrapper to maintain backward compatibility with existing routes.
    Internally calls ElasticClient.hybrid_search().
    """
    from app.services.elastic_client import ElasticClient
    client = ElasticClient()
    return client.hybrid_search(req)
