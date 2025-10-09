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
    education: List[str] = []
    hospitals: List[str] = []

    reputation_score: Optional[float] = 0.0
    factors: Optional[Dict[str, float]] = None
    citations: Optional[List[str]] = None  # source_ids for reference


class SearchResponse(BaseModel):
    candidates: List[DoctorHit] = []


class RatingRecord(BaseModel):
    """Schema for a single rating/review record."""
    source: str = Field(
        description="Name of the review platform. (e.g. ZocDoc)")
    score: float = Field(description="The numerical rating (e.g. 4.5, 5.0).")
    count: int = Field(
        description=
        "The total number of patient reviews counted from this source.")
    link: str = Field(description="URL to the original review page.")


class EnrichedProfileData(BaseModel):
    """The final structured data object to be extracted by the LLM."""
    years_experience: int = Field(
        description=
        "Total years of clinical practice since residency/fellowship completion, calculated by LLM."
    )
    profile_picture_url: str = Field(
        description=
        "Public URL found for the doctor's portrait or profile image.")
    bio_text_consolidated: str = Field(
        description=
        "Comprehensive biographical paragraph summarizing the doctor's experience, education, and special interests."
    )
    publications: List[str] = Field(
        description=
        "A list of titles of 3-5 key professional publications or research papers."
    )
    ratings_summary: List[RatingRecord] = Field(
        description=
        "List of structured rating records from all unique platforms found.")
    testimonial_summary_text: str = Field(
        description=
        "Summary of key patient testimonials and overall feedback to help new patients"
    )
    top_education: List[str] = Field(
        description=
        "A list of 1-3 prominent medical schools, universities, or residencies attended."
    )
    top_hospitals: List[str] = Field(
        description=
        "A list of 1-3 major hospitals or clinics where the doctor holds current privileges or works."
    )


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


# New schemas for frontend integration
class FrontendSearchRequest(BaseModel):
    query: Optional[str] = None
    location: Optional[str] = None
    insurance: Optional[str] = None


class FrontendDoctor(BaseModel):
    id: int
    name: str
    specialty: str
    rating: float
    reviews: int
    address: str
    lat: float
    lng: float
    time: str
    img: str = "/doctor.png"
    insurance_accepted: Optional[List[str]] = None


class FrontendSearchResponse(BaseModel):
    doctors: List[FrontendDoctor]
    search_query: Optional[str] = None
    total_results: int


class VoiceSearchRequest(BaseModel):
    voice_query: Optional[str] = None