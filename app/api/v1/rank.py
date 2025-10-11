from fastapi import APIRouter, Depends
from ...models.schemas import RankRequest, RankResponse
from ...services.ranker import rank_candidates

router = APIRouter()


@router.post("/rank", response_model=RankResponse)
def rank(req: RankRequest):
    ranked = rank_candidates(req)
    return RankResponse(ranked=ranked)
