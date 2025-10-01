from fastapi import APIRouter, Depends
from ...models.schemas import SearchRequest, SearchResponse
from ...services.elastic_client import hybrid_search
from ...deps import get_elastic

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
def search(req: SearchRequest, es=Depends(get_elastic)):
    hits = hybrid_search(es, req)
    return SearchResponse(candidates=hits)
