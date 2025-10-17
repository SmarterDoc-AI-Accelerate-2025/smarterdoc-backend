from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
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
        "A list of 1-3 prominent medical schools/universities/residencies attended."
    )
    top_hospitals: List[str] = Field(
        description=
        "A list of 1-4 major hospitals or clinics where the doctor holds current privileges or works."
    )
    latitude: float = Field(
        description=
        "The decimal latitude coordinate of the primary practice location.")
    longitude: float = Field(
        description=
        "The decimal longitude coordinate of the primary practice location.")


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


# ============================================
# Frontend Schemas
# ============================================


# New schemas for frontend integration
class FrontendSearchRequest(BaseModel):
    specialty: Optional[str] = None
    min_experience: Optional[int] = None
    has_certification: Optional[bool] = False
    limit: Optional[int] = 30


# Frontend Response
class DoctorOut(BaseModel):
    npi: str
    first_name: Optional[str]
    last_name: Optional[str]
    primary_specialty: Optional[str]
    years_experience: Optional[int]
    bio: Optional[str] = None
    testimonial_summary_text: Optional[str] = None
    publications: Optional[List[str]] = None
    certifications: Optional[List[str]] = None
    education: Optional[List[str]] = None
    hospitals: Optional[List[str]] = None
    ratings: Optional[List[RatingRecord]] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None

    profile_picture_url: Optional[str] = None


class FrontendSearchResponse(BaseModel):
    search_query: Optional[str]
    total_results: int
    doctors: List[DoctorOut]


# TODO: for mock data, may remove, see DoctorOut() for response schema
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


# ============================================
# AI Chat Schemas
# ============================================


class ChatMessage(BaseModel):
    """Single chat message."""
    role: str = Field(...,
                      description="Role of the message sender (user/model)")
    content: str = Field(..., description="Content of the message")


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str = Field(...,
                         description="User message to send to the AI",
                         min_length=1)
    history: Optional[List[ChatMessage]] = Field(
        default=None, description="Previous conversation history")
    model: Optional[str] = Field(
        default=None,
        description="Model to use for generation (e.g., gemini-2.0-flash-001)")
    temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Controls randomness in generation")
    max_tokens: Optional[int] = Field(
        default=None, gt=0, description="Maximum number of tokens to generate")
    system_instruction: Optional[str] = Field(
        default=None,
        description="System instruction to guide the model's behavior")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    model_config = ConfigDict(protected_namespaces=())

    message: str = Field(..., description="AI-generated response")
    role: str = Field(default="model", description="Role of the responder")
    model_used: str = Field(..., description="Model used for generation")
    usage: Optional[Dict[str,
                         Any]] = Field(default=None,
                                       description="Token usage information")
    finish_reason: Optional[str] = Field(
        default=None, description="Reason why generation finished")


class ChatStreamRequest(BaseModel):
    """Request model for streaming chat endpoint."""
    message: str = Field(...,
                         description="User message to send to the AI",
                         min_length=1)
    history: Optional[List[ChatMessage]] = Field(
        default=None, description="Previous conversation history")
    model: Optional[str] = Field(default=None,
                                 description="Model to use for generation")
    temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Controls randomness in generation")
    system_instruction: Optional[str] = Field(
        default=None,
        description="System instruction to guide the model's behavior")


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    model: str


# ============================================
# Speech-to-Text Schemas
# ============================================


class SpeechStreamRequest(BaseModel):
    """Request model for streaming speech transcription."""
    language_code: Optional[str] = Field(
        default=None, description="Language code (e.g., 'en-US', 'zh-CN')")
    single_utterance: Optional[bool] = Field(
        default=None, description="Stop listening after single utterance")
    duration_seconds: Optional[int] = Field(
        default=None,
        gt=0,
        description="Maximum recording duration in seconds")


class SpeechTranscriptionResult(BaseModel):
    """Result model for speech transcription."""
    transcript: str = Field(..., description="Transcribed text")
    is_final: Optional[bool] = Field(
        default=None, description="Whether this is a final result")
    confidence: Optional[float] = Field(
        default=None, description="Confidence score (0-1) for final results")
    stability: Optional[float] = Field(
        default=None, description="Stability score (0-1) for interim results")


class VoiceSearchRequest(BaseModel):
    voice_query: Optional[str] = None


# ============================================
# RAG Output Schemas
# ============================================


class FinalRecommendedDoctor(BaseModel):
    """The final doctor profile with the score and LLM-generated reasoning."""
    npi: str
    # first_name: str
    # last_name: str
    # final_weighted_score: float = Field(
    #     description="The final score calculated by the Python ranker.")
    # agent_reasoning_summary: str = Field(
    #     description=
    #     "The LLM-generated, concise justification (max 5 sentences) for why this doctor was selected."
    # )


class FinalRecommendationList(BaseModel):
    """The container for the structured list of Top 3 doctors returned by the RAG Agent."""
    recommendations: List[FinalRecommendedDoctor]


class AgentSearchRequest(BaseModel):
    """The unified input for the Hybrid Search RAG pipeline."""
    specialty: str = Field(
        description=
        "The primary medical specialty to search for (e.g., 'OBGYN').")
    query: str = Field(
        description=
        "The user's free-text request (e.g., 'board certified doctor who's patient and has extensive experience in fertility treatments')."
    )


class AgentSearchResponse(BaseModel):
    """The final response containing the ranked list of full doctor profiles."""
    doctors: List[DoctorOut]
    total_results: int = Field(default=30)
    search_query: str
