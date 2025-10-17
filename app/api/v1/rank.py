from fastapi import APIRouter, Depends, HTTPException
from ...models.schemas import (
    RankRequest, RankResponse, 
    FrontendSearchResponse, SimpleSearchRequest
)
from ...services.ranker import rank_candidates, search_and_rank_doctors_service

router = APIRouter()

@router.post("/rank", response_model=RankResponse)
def rank(req: RankRequest):
    ranked = rank_candidates(req)
    return RankResponse(ranked=ranked)


@router.post("/search-rank", response_model=FrontendSearchResponse)
def search_and_rank_doctors(req: SimpleSearchRequest):
    """
    搜索医生并通过ranker进行智能排序
    接受新的数据格式: {"specialty": STRING, "query": STRING}
    返回前端需要的格式数据
    """
    try:
        # 调用服务层函数处理业务逻辑
        return search_and_rank_doctors_service(req.specialty, req.query)
        
    except Exception as e:
        print("Search and rank error:", e)
        raise HTTPException(status_code=500, detail="Doctor search and ranking failed.")
