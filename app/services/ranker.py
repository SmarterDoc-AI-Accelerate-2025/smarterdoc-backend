from app.models.schemas import DoctorHit, DoctorOut, RankRequest, FrontendRankSearchRequest, FrontendSearchResponse
from typing import List
from .bq_doctor_service import BQDoctorService

MOCK = DoctorHit(npi="1234567890",
          name="Dr. Mock Specialist",
          specialties=["Orthopedic Surgery", "Sports Medicine"],
          metro="nyc",
          distance_km=4.2,
          in_network=True,
          reputation_score=0.95,
          factors={
              "Experience": 25.0,
              "Network": 30.0
          },
          citations=["PubMed(2023)", "Hospital Profile"],
          education=[
              "NYU School of Medicine",
              "Hospital for Special Surgery Residency"
          ],
          hospitals=["NYU Langone", "Mount Sinai"])

# Define the structure for the tool call
def calculate_recommendation_score(
        doctors: list[dict],  # List of dicts containing the 30 doctor profiles
        insurance_weight: float = 0.0,
        hospital_weight: float = 0.0,
        specialty_weight: float = 0.0,
        review_weight: float = 0.0) -> list[dict]:
    """
    Calculates a final personalized score for a list of doctors based on
    dynamically provided user preference weights.
    """
    # 1. Normalize weights if necessary (sum to 1.0)
    # 2. Implement the scoring logic (e.g., Final_Score = w1*feature1 + w2*feature2 + ...)
    #    (This logic MUST be robust and purely deterministic Python code.)

    # Example: score based on average rating and hospital tier
    for doc in doctors:
        doc['final_score'] = (
            (doc.get('ratings_avg', 0) * review_weight) +
            (doc.get('hospital_tier', 0) * hospital_weight) +
            (doc.get('semantic_similarity', 0) * specialty_weight
             )  # Use semantic similarity as a feature
        )

    # 3. Sort and return the top 3
    doctors.sort(key=lambda x: x['final_score'], reverse=True)
    return doctors[:3]


def rank_candidates(req):
    return [MOCK]  # Return mock data for now


def search_and_rank_doctors_service(req: FrontendRankSearchRequest, bq_service: BQDoctorService) -> FrontendSearchResponse:
    """
    搜索医生并通过ranker进行智能排序的服务函数
    接受新的数据格式: specialty, insurance, location, userinput
    返回与search.py相同的FrontendSearchResponse格式
    """
    # 1. 先通过BigQuery搜索基础医生列表
    doctors = bq_service.search_doctors(
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
