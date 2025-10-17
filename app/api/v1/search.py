from fastapi import APIRouter, Depends, HTTPException
from typing import List
from ...models.schemas import (SearchRequest, SearchResponse,
                               FrontendSearchRequest, FrontendSearchResponse,
                               VoiceSearchRequest, AgentSearchRequest,
                               AgentSearchResponse)
from ...deps import get_bq, get_bq_doctor_service
from ...services.mock_doctor_service import mock_doctor_service
from app.services.bq_doctor_service import BQDoctorService
from google.cloud import bigquery

router = APIRouter()

# 常见医生专科列表
SPECIALTIES = [
    "Family Medicine",
    "Internal Medicine",
    "Pediatrics",
    "Cardiology",
    "Dermatology",
    "Emergency Medicine",
    "Endocrinology",
    "Gastroenterology",
    "General Surgery",
    "Geriatrics",
    "Hematology",
    "Infectious Disease",
    "Nephrology",
    "Neurology",
    "Neurosurgery",
    "Obstetrics & Gynecology",
    "Oncology",
    "Ophthalmology",
    "Orthopedic Surgery",
    "Otolaryngology (ENT)",
    "Pathology",
    "Physical Medicine & Rehabilitation",
    "Plastic Surgery",
    "Psychiatry",
    "Pulmonology",
    "Radiology",
    "Rheumatology",
    "Urology",
    "Anesthesiology",
    "Allergy & Immunology"
]

# 常见保险公司列表
INSURANCE_PLANS = [
    "Aetna",
    "Anthem Blue Cross Blue Shield",
    "Blue Cross Blue Shield",
    "Cigna",
    "UnitedHealthcare",
    "Humana",
    "Kaiser Permanente",
    "Medicare",
    "Medicaid",
    "Oscar Health",
    "Molina Healthcare",
    "Centene",
    "WellCare",
    "Tricare",
    "Bright Health",
    "Ambetter",
    "Health Net",
    "MetLife",
    "Guardian",
    "Delta Dental",
    "VSP Vision Care",
    "EyeMed",
    "Aflac",
    "Optum",
    "Coventry Health Care"
]

# @router.post("", response_model=SearchResponse)
# def search(req: SearchRequest, es=Depends(get_elastic)):
#     """
#     Original search endpoint - at /v1/search
#     """
#     try:
#         hits = hybrid_search(req, es)
#         return SearchResponse(candidates=hits)
#     except Exception as e:
#         # Log the error for debugging
#         print(f"Error in hybrid_search: {str(e)}")
#         raise HTTPException(status_code=500,
#                             detail=f"Search service error: {str(e)}")


@router.post("/doctors", response_model=FrontendSearchResponse)
def search_doctors(
    req: FrontendSearchRequest,
    bq_service: BQDoctorService = Depends(get_bq_doctor_service)):
    """
    Real-time doctor search from BigQuery.
    Filters: specialty, years_experience, certification.
    """
    try:
        doctors = bq_service.search_doctors(
            specialty=req.specialty,
            min_experience=req.min_experience,
            has_certification=req.has_certification,
            limit=req.limit or 30)
        return FrontendSearchResponse(doctors=doctors,
                                      total_results=len(doctors),
                                      search_query=req.specialty)
    except Exception as e:
        print("BQ search error:", e)
        raise HTTPException(status_code=500, detail="Doctor search failed.")


@router.post("/voice", response_model=FrontendSearchResponse)
def voice_search(req: VoiceSearchRequest):
    """
    Mock voice search doctors endpoint for frontend integration
    Now at /v1/search/voice
    """
    try:
        doctors = mock_doctor_service.voice_search_doctors(req.voice_query)

        return FrontendSearchResponse(doctors=doctors,
                                      search_query=req.voice_query,
                                      total_results=len(doctors))
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"Voice search failed: {str(e)}")


@router.post("/recommendations", response_model=AgentSearchResponse)
async def get_recommended_doctors(
    req: AgentSearchRequest,
    # Use the BQDoctorService singleton dependency (which already has the BQ client)
    bq_service: BQDoctorService = Depends(get_bq_doctor_service)):
    """
    Executes the multi-stage Hybrid Search RAG pipeline:
    1. Generates Dense (query) and Sparse (specialty) vectors.
    2. Queries Vertex AI Vector Search (Hybrid Search + RRF).
    3. LLM determines dynamic ranking weights.
    4. Python re-ranks candidates by weighted scores.
    5. Batch look-up enriches final candidates from BigQuery.
    """
    try:
        # The BQ service wrapper calls the RagAgentService, which performs
        # the entire orchestration and returns the final, ordered list of 30 profiles.

        # The BQDoctorService method is designed to take a Dict[str, Any]
        # which is the pydantic model converted to a dictionary.
        request_data = req.model_dump()

        # The final result is the list of 30 doctors, ordered by the LLM-guided score
        doctors = await bq_service.get_agent_recommended_doctors(request_data)

        return AgentSearchResponse(
            doctors=doctors,
            total_results=len(doctors),
            search_query=f"Specialty: {req.specialty} | Query: {req.query}")
    except Exception as e:
        # Log the detailed error, but return a generic 500 error to the client
        print("RAG Pipeline execution error:", e)
        raise HTTPException(status_code=500,
                            detail="Recommendation pipeline failed.")


@router.get("/specialties", response_model=List[str])
def get_specialties():
    """
    Get list of medical specialties for dropdown selection.
    Returns a predefined list of common medical specialties.
    Endpoint: GET /api/v1/search/specialties
    """
    return SPECIALTIES


@router.get("/specialties/from-bq", response_model=List[str])
def get_specialties_from_bigquery(bq: bigquery.Client = Depends(get_bq)):
    """
    Get list of medical specialties from BigQuery database.
    Queries the doctor_profiles table for all distinct primary_specialty values.
    Returns a sorted list of unique specialties actually present in the database.
    Endpoint: GET /api/v1/search/specialties/from-bq
    """
    try:
        svc = BQDoctorService(client=bq)
        specialties = svc.get_all_specialties()
        return specialties
    except Exception as e:
        print("Error fetching specialties from BigQuery:", e)
        raise HTTPException(status_code=500, 
                          detail=f"Failed to fetch specialties from database: {str(e)}")


@router.get("/insurance-plans", response_model=List[str])
def get_insurance_plans():
    """
    Get list of insurance plans for dropdown selection.
    Returns a predefined list of common insurance providers in the US.
    Endpoint: GET /api/v1/search/insurance-plans
    """
    return INSURANCE_PLANS

