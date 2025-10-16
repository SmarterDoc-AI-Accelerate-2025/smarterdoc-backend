from fastapi import APIRouter, Depends, HTTPException
from ...models.schemas import (SearchRequest, SearchResponse,
                               FrontendSearchRequest, FrontendSearchResponse,
                               VoiceSearchRequest)
from ...deps import get_bq
from ...services.mock_doctor_service import mock_doctor_service
from app.services.bq_doctor_service import BQDoctorService
from google.cloud import bigquery

router = APIRouter()


@router.post("/doctors", response_model=FrontendSearchResponse)
def search_doctors(req: FrontendSearchRequest,
                   bq: bigquery.Client = Depends(get_bq)):
    """
    Real-time doctor search from BigQuery.
    Filters: specialty, years_experience, certification.
    """
    try:
        svc = BQDoctorService(client=bq)
        doctors = svc.search_doctors(specialty=req.specialty,
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
