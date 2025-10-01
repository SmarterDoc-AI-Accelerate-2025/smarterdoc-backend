from fastapi import APIRouter, Depends
from ...models.schemas import RankRequest, RankResponse
from ...services.ranker import rank_candidates
from ...deps import get_elastic

router = APIRouter()


@router.post("/rank", response_model=RankResponse)
def rank(req: RankRequest, es=Depends(get_elastic)):
    ranked = rank_candidates(req, es=es)
    return RankResponse(ranked=ranked)
