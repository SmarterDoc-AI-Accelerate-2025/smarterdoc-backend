from fastapi import APIRouter, Depends, HTTPException
from ...models.schemas import (
    RankRequest, RankResponse, 
    FrontendRankSearchRequest, FrontendSearchResponse
)
from ...services.ranker import rank_candidates, search_and_rank_doctors_service
from ...services.bq_doctor_service import BQDoctorService
from ...deps import get_bq
from google.cloud import bigquery

router = APIRouter()

@router.post("/rank", response_model=RankResponse)
def rank(req: RankRequest):
    ranked = rank_candidates(req)
    return RankResponse(ranked=ranked)


@router.post("/search-rank", response_model=FrontendSearchResponse)
def search_and_rank_doctors(
    req: FrontendRankSearchRequest,
    bq: bigquery.Client = Depends(get_bq)
):
    """
    搜索医生并通过ranker进行智能排序
    接受新的数据格式: specialty, insurance, location, userinput
    返回与search.py相同的FrontendSearchResponse格式
    """
    try:
        # 创建BigQuery服务实例
        bq_service = BQDoctorService(client=bq)
        
        # 调用服务层函数处理业务逻辑
        return search_and_rank_doctors_service(req, bq_service)
        
    except Exception as e:
        print("Search and rank error:", e)
        raise HTTPException(status_code=500, detail="Doctor search and ranking failed.")
