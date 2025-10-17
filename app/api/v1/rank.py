from fastapi import APIRouter, Depends, HTTPException
from typing import List
from ...models.schemas import (
    RankRequest, RankResponse, 
    FrontendRankSearchRequest, FrontendSearchResponse,
    DoctorOut, DoctorHit
)
from ...services.ranker import rank_candidates
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
        # 1. 先通过BigQuery搜索基础医生列表
        # 这里的参数需要修改
        svc = BQDoctorService(client=bq)
        doctors = svc.search_doctors(
            specialty=req.specialty,
            min_experience=10,
            has_certification=True,
            limit=30
        )
        
        if not doctors:
            return FrontendSearchResponse(
                doctors=[],
                total_results=0,
                search_query=req.userinput or req.specialty
            )
        
        # 2. 转换为DoctorHit格式供ranker使用
        doctor_hits = convert_to_doctor_hits(doctors)
        
        # 3. 调用ranker进行智能排序
        rank_request = RankRequest(
            condition_slug=req.specialty or "",
            insurance_plan=req.insurance,
            user_location=parse_location(req.location),
            candidates=doctor_hits
        )
        
        ranked_doctors = rank_candidates(rank_request)
        
        # 4. 转换回前端格式
        frontend_doctors = convert_to_frontend_format(ranked_doctors, doctors)
        
        return FrontendSearchResponse(
            doctors=frontend_doctors,
            total_results=len(frontend_doctors),
            search_query=req.userinput or req.specialty
        )
        
    except Exception as e:
        print("Search and rank error:", e)
        raise HTTPException(status_code=500, detail="Doctor search and ranking failed.")


def parse_location(location_str: str) -> List[float]:
    """
    将位置字符串解析为[纬度, 经度]
    暂时返回默认位置，后续可以集成地理编码服务
    """
    if not location_str:
        return None
    
    # 这里可以集成地理编码服务来解析真实位置
    # 暂时返回纽约默认位置
    return [40.7128, -74.0060]


def convert_to_doctor_hits(doctors: List[DoctorOut]) -> List[DoctorHit]:
    """将DoctorOut转换为DoctorHit格式供ranker使用"""
    doctor_hits = []
    
    for doc in doctors:
        hit = DoctorHit(
            npi=doc.npi,
            name=f"{doc.first_name or ''} {doc.last_name or ''}".strip(),
            specialties=[doc.primary_specialty] if doc.primary_specialty else [],
            metro=None,  # 可以从location解析
            distance_km=None,  # 可以根据用户位置计算
            in_network=None,  # 可以根据insurance判断
            reputation_score=0.8,  # 默认分数，可以基于ratings计算
            factors={
                "Experience": float(doc.years_experience or 0),
                "Network": 30.0,  # 默认值
                "Reviews": 25.0   # 默认值
            },
            citations=doc.publications or [],
            education=doc.education or [],
            hospitals=doc.hospitals or []
        )
        doctor_hits.append(hit)
    
    return doctor_hits


def convert_to_frontend_format(ranked_doctors: List[DoctorHit], original_doctors: List[DoctorOut]) -> List[DoctorOut]:
    """
    将排序后的DoctorHit转换回前端DoctorOut格式
    保持ranker的排序顺序
    """
    # 创建NPI到原始医生数据的映射
    npi_to_doctor = {doc.npi: doc for doc in original_doctors}
    
    # 按照ranker的排序顺序返回医生数据
    frontend_doctors = []
    for ranked_doc in ranked_doctors:
        if ranked_doc.npi in npi_to_doctor:
            frontend_doctors.append(npi_to_doctor[ranked_doc.npi])
    
    return frontend_doctors
