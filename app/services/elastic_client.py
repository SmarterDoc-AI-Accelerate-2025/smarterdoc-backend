from elasticsearch import Elasticsearch, helpers
from typing import List, Dict, Any

from app.config import settings
from app.util.logging import logger
from ..models.schemas import SearchRequest, DoctorHit


class ElasticClient:
    """
    Client for managing connections and operations (indexing, searching) 
    with Elastic Cloud.
    """

    def __init__(self):
        """Initializes the Elasticsearch client."""
        try:
            self.es = Elasticsearch(
                cloud_id=settings.
                ELASTIC_URL,
                api_key=settings.ELASTIC_API_KEY,
                request_timeout=30
            )
            self.es.info()
            logger.info("Successfully connected to Elastic Cloud.")
        except Exception as e:
            logger.error(f"Failed to connect to Elastic Cloud: {e}")
            self.es = None

    def bulk_upsert(self, records: List[Dict[str, Any]],
                    index_name: str) -> int:
        """
        Performs a bulk upsert operation on Elasticsearch.
        Uses the 'npi' field as the unique document ID.
        """
        if not self.es:
            logger.error(
                "Elasticsearch client is not initialized. Skipping upsert.")
            return 0

        def generate_actions():
            for record in records:
                source_doc = record.copy()

                doc_id = str(source_doc.pop('npi'))

                action = {
                    "_index": index_name,
                    "_id": doc_id,
                    "_source": source_doc,
                    "_op_type": "index"
                }
                yield action

        try:
            successes, errors = helpers.bulk(
                self.es,
                generate_actions(),
                chunk_size=100,  
                max_retries=3,
                raise_on_error=False 
            )

            if errors:
                logger.warning(
                    f"Elasticsearch bulk indexing completed with {len(errors)} errors."
                )

            logger.info(
                f"Successfully indexed/updated {successes} documents in index '{index_name}'."
            )
            return successes

        except Exception as e:
            logger.error(f"FATAL ERROR during Elastic bulk upsert: {e}")
            return 0

    # The following are placeholder methods for the backend API (not the Indexer job)

    def hybrid_search(self, req: SearchRequest) -> list[DoctorHit]:
        """Placeholder for hybrid (BM25 + vector) search logic."""
        logger.warning("Hybrid search is a placeholder.")
        return []

    def fetch_evidence_ids(self,
                           npi: str,
                           condition_slug: str,
                           limit: int = 3) -> list[str]:
        """Placeholder for fetching evidence documents related to a doctor."""
        logger.warning("Fetch evidence is a placeholder.")
        return []
