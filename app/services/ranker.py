from app.models.schemas import DoctorHit
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Union, Literal
from app.models.schemas import FinalRecommendedDoctor
from pydantic import ValidationError
from app.util.hospitals import HOSPITAL_TIERS
from app.util.med_schools import MED_SCHOOL_TIERS
from app.models.schemas import DoctorHit, DoctorOut, FrontendSearchResponse
from typing import List

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


def rank_candidates(req):
    return MOCK


# --- 1. List Features for Dynamic Weighting ---
MAIN_FEATURES = {
    "semantic_score": 0.5,  # core k-NN similarity score
    "affiliated_hospitals": 0.2,  # Hospital tier/match
    "experience_years": 0.25,  # Years of clinical experience
    "reputation_rating": 0.35,  # Average patient rating/score
    "publications_count": 0.1,  # Count of recent/relevant publications
    "certification_match": 0.5,  # Specific certification match
    "education_tier": 0.1  # Tier of medical school/residency
}


# --- 2. Pydantic Schema for the LLM Tool Call ---
# This schema uses the keys from MAIN_FEATURES and is what the LLM MUST generate.
class DynamicRankingWeights(BaseModel):
    """Schema for the LLM to output a weight for every feature in the master list."""
    semantic_score: float = Field(
        default=MAIN_FEATURES["semantic_score"],
        description=
        "Weight (0.0 to 1.0) for the initial k-NN semantic similarity from vector search. High if the query is nuanced."
    )

    affiliated_hospitals: float = Field(
        default=MAIN_FEATURES["affiliated_hospitals"],
        description=
        "Weight (0.0 to 1.0) for affiliation with specific/top-tier hospitals if mentioned in the query. If the keywords 'best' or 'top' are mentioned assign higher weights."
    )
    experience_years: float = Field(
        default=MAIN_FEATURES["experience_years"],
        description=
        "Weight (0.0 to 1.0) for the doctor's years of experience (higher if user mentions 'seasoned', 'experienced', or 'long history' etc)."
    )
    reputation_rating: float = Field(
        default=MAIN_FEATURES["reputation_rating"],
        description=
        "Weight (0.0 to 1.0) for the average patient star rating and review sentiment."
    )
    publications_count: float = Field(
        default=MAIN_FEATURES["publications_count"],
        description=
        "Weight (0.0 to 1.0) for the doctor having recent publications or being research-focused or has expertise in the specific field the query asks for."
    )
    certification_match: float = Field(
        default=MAIN_FEATURES["certification_match"],
        description=
        "Weight (0.0 to 1.0) for **general** or **specific** Board Certification matches (e.g., MFM, Reproductive Endo)."
    )
    education_tier: float = Field(
        default=MAIN_FEATURES["education_tier"],
        description=
        "Weight (0.0 to 1.0) for the quality/tier of medical school and residency. Assign higher weights only if query specifically states the importance of med school, otherwise default < 0.05."
    )


# --- 3. The LLM Tool Function (Modified) ---


def generate_ranking_weights(**kwargs: float) -> Dict[str, float]:
    """
    [LLM TOOL] Validates LLM-generated weights against the Pydantic schema 
    and ensures only valid floats are returned.
    
    The LLM calls this function to pass its determined weights.
    """
    try:
        # Pydantic validates the input arguments based on the schema
        weights = DynamicRankingWeights(**kwargs)
        return weights.model_dump()
    except ValidationError:
        # Fallback: If the LLM generates junk, return default safe weights
        return DynamicRankingWeights().model_dump()


# --- 4. The Reranking Logic (Modified to accept generic weights) ---


def _normalize_experience(years: int) -> float:
    """Normalizes experience (e.g., max 30 years) to a 0.0 - 1.0 score."""
    MAX_EXP = 30.0
    return min(years / MAX_EXP, 1.0)


def _get_avg_rating(ratings_list: List[Dict[str, Any]]) -> float:
    """Calculates the single average rating score from multiple sources."""
    if not ratings_list: return 0.0
    # Assuming all scores are 5.0 scale, this is just a placeholder
    total_score = sum(r.get('score', 0) for r in ratings_list)
    return min(total_score / (5.0 * len(ratings_list)),
               1.0)  # Simple average normalization


def _calculate_tier_score(affiliations: List[str],
                          tier_map: Dict[str, List[str]]) -> float:
    """Returns the highest tier score found (1.0 for Tier 1, 0.5 for Tier 2)."""
    score_map = {"Tier_1": 1.0, "Tier_2": 0.5, "Tier_3": 0.2, "Default": 0.1}
    max_score = 0.0

    for affiliation in affiliations:
        for tier, institutions in tier_map.items():
            if affiliation in institutions:
                max_score = max(max_score, score_map.get(tier, 0.1))

    return max_score


def apply_personalized_reranking(
        candidates: List[Dict[str, Any]],
        weights: Dict[str, float]) -> List[FinalRecommendedDoctor]:
    """
    Applies the personalized, weighted formula to the k-NN candidates.
    """

    # 1. Normalize Weights (Optional but recommended to keep scores comparable)
    # total_weight = sum(weights.values())
    # if total_weight == 0: total_weight = 1.0

    scored_candidates = []

    for doc in candidates:

        normalized_rating = _get_avg_rating(doc.get('ratings', []))
        normalized_experience = _normalize_experience(
            doc.get('years_experience', 0))
        hospital_tier_score = _calculate_tier_score(doc.get('hospitals', []),
                                                    HOSPITAL_TIERS)
        education_tier_score = _calculate_tier_score(doc.get('education', []),
                                                     MED_SCHOOL_TIERS)
        semantic_sim_score = doc.get('semantic_similarity_score', 0.0)
        cert_match_score = 1.0 if doc.get('certifications') else 0.0
        pub_score = 1.0 if doc.get('publications') else 0.0

        features = {
            "semantic_score": semantic_sim_score,
            "reputation_rating": normalized_rating,
            "experience_years": normalized_experience,
            "affiliated_hospitals": hospital_tier_score,
            "education_tier": education_tier_score,
            "certification_match": cert_match_score,
            "publications_count": pub_score,
        }

        # 2. Calculate Final Score using Dynamic Weights
        final_score = 0.0
        for key, weight in weights.items():
            final_score += features.get(key, 0.0) * weight

        doc['final_weighted_score'] = final_score
        doc['feature_scores'] = features

        # ranked_doctors.append(
        #     RecommendedDoctor(
        #         npi=doc['npi'],
        #         first_name=doc.get('first_name', ''),
        #         last_name=doc.get('last_name', ''),
        #         final_recommendation_score=final_score).model_dump())
        scored_candidates.append(doc)

    scored_candidates.sort(key=lambda x: x['final_weighted_score'],
                           reverse=True)

    return scored_candidates[:10]
def rank_candidates(specialty: str, query: str) -> List[DoctorOut]:
    """
    对医生候选列表进行智能排序
    接受专科和查询条件，返回排序后的医生列表
    """
    # TODO: 实现具体的排序算法
    # 目前返回mock数据作为占位符
    return []


def search_and_rank_doctors_service(specialty: str, query: str) -> FrontendSearchResponse:
    """
    搜索医生并通过ranker进行智能排序的服务函数
    接受新的数据格式: {"specialty": STRING, "query": STRING}
    返回前端需要的格式数据
    """
    # 调用ranker进行智能排序
    ranked_doctors = rank_candidates(specialty, query)
    
    return FrontendSearchResponse(
        doctors=ranked_doctors,
        total_results=len(ranked_doctors),
        search_query=query
    )


