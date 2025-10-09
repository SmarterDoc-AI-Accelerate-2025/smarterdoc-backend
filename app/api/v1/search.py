from fastapi import APIRouter, Depends, HTTPException
from ...models.schemas import (
    SearchRequest, 
    SearchResponse, 
    FrontendSearchRequest, 
    FrontendSearchResponse,
    VoiceSearchRequest
)
from ...services.elastic_client import hybrid_search
from ...deps import get_elastic
from ...services.mock_doctor_service import mock_doctor_service

router = APIRouter()

@router.post("", response_model=SearchResponse)
def search(req: SearchRequest, es=Depends(get_elastic)):
    """
    Original search endpoint - at /v1/search
    """
    try:
        hits = hybrid_search(req, es)
        return SearchResponse(candidates=hits)
    except Exception as e:
        # Log the error for debugging
        print(f"Error in hybrid_search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search service error: {str(e)}")

@router.post("/doctors", response_model=FrontendSearchResponse)
def search_doctors(req: FrontendSearchRequest):
    """
    Mock search doctors endpoint for frontend integration
    Now at /v1/search/doctors
    """
    try:
        doctors = mock_doctor_service.search_doctors(req)
        
        return FrontendSearchResponse(
            doctors=doctors,
            search_query=req.query,
            total_results=len(doctors)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.post("/voice", response_model=FrontendSearchResponse)
def voice_search(req: VoiceSearchRequest):
    """
    Mock voice search doctors endpoint for frontend integration
    Now at /v1/search/voice
    """
    try:
        doctors = mock_doctor_service.voice_search_doctors(req.voice_query)
        
        return FrontendSearchResponse(
            doctors=doctors,
            search_query=req.voice_query,
            total_results=len(doctors)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice search failed: {str(e)}")