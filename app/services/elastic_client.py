from elasticsearch import Elasticsearch
from ..models.schemas import SearchRequest, DoctorHit


# TODO: implement
def hybrid_search(es: Elasticsearch, req: SearchRequest) -> list[DoctorHit]:
    return []


def fetch_evidence_ids(es: Elasticsearch,
                       npi: str,
                       condition_slug: str,
                       limit: int = 3) -> list[str]:
    return []
