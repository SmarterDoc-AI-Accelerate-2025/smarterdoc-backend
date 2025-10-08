from fastapi import APIRouter, Depends
from ...models.schemas import SearchRequest, SearchResponse
from ...services.elastic_client import hybrid_search
from ...deps import get_elastic

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
def search(req: SearchRequest, es=Depends(get_elastic)):
    # The 'es' parameter from Depends(get_elastic) is currently ignored
    # because hybrid_search is a mock function that doesn't need it.
    hits = hybrid_search(req, es)
    return SearchResponse(candidates=hits)
