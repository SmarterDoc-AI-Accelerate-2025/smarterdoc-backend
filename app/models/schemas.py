from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from .enums import MetroSlug


class SearchRequest(BaseModel):
    query: str
    insurance_plan: Optional[str] = None
    metro: Optional[MetroSlug] = None
    radius_km: int = 20
    limit: int = 50


class DoctorHit(BaseModel):
    npi: str
    name: str
    specialties: List[str] = []
    metro: Optional[MetroSlug] = None
    distance_km: Optional[float] = None
    in_network: Optional[bool] = None
    reputation_score: Optional[float] = 0.0
    factors: Optional[Dict[str, float]] = None
    citations: Optional[List[str]] = None  # source_ids for reference


class SearchResponse(BaseModel):
    candidates: List[DoctorHit] = []


# Rank
class RankRequest(BaseModel):
    condition_slug: str
    insurance_plan: Optional[str] = None
    user_location: Optional[
        List[float]] = None  # [lat, lon] for precise location
    candidates: List[DoctorHit]


class RankResponse(BaseModel):
    ranked: List[DoctorHit]


class EstimateRequest(BaseModel):
    condition_slug: str
    metro: str


class EstimateResponse(BaseModel):
    costs: Dict[str, Dict[str, float]]  # {cpt_code: {low, median, high}}


# Book
class BookRequest(BaseModel):
    npi: str
    user_name: str
    preferred_times: List[str]
    reason: str
    callback_number: str


class BookResponse(BaseModel):
    status: str
    message: str
