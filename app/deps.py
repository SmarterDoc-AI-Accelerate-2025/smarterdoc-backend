######################
# Dependencies to reuse
######################

from elasticsearch import Elasticsearch
from .config import settings

_es_client: Elasticsearch | None = None


def get_elastic() -> Elasticsearch:
    global _es_client
    if _es_client is None:
        api_key = settings.ELASTIC_API_KEY
        kwargs = {"hosts": [settings.ELASTIC_URL]}
        if api_key:
            kwargs["api_key"] = api_key
        _es_client = Elasticsearch(**kwargs)
    return _es_client
