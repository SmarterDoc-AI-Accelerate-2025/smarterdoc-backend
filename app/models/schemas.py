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


# ============================================
# AI Chat Schemas
# ============================================

class ChatMessage(BaseModel):
    """Single chat message."""
    role: str = Field(..., description="Role of the message sender (user/model)")
    content: str = Field(..., description="Content of the message")


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str = Field(..., description="User message to send to the AI", min_length=1)
    history: Optional[List[ChatMessage]] = Field(
        default=None, 
        description="Previous conversation history"
    )
    model: Optional[str] = Field(
        default=None, 
        description="Model to use for generation (e.g., gemini-2.0-flash-001)"
    )
    temperature: Optional[float] = Field(
        default=None, 
        ge=0.0, 
        le=2.0, 
        description="Controls randomness in generation"
    )
    max_tokens: Optional[int] = Field(
        default=None, 
        gt=0, 
        description="Maximum number of tokens to generate"
    )
    system_instruction: Optional[str] = Field(
        default=None,
        description="System instruction to guide the model's behavior"
    )


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    model_config = ConfigDict(protected_namespaces=())
    
    message: str = Field(..., description="AI-generated response")
    role: str = Field(default="model", description="Role of the responder")
    model_used: str = Field(..., description="Model used for generation")
    usage: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Token usage information"
    )
    finish_reason: Optional[str] = Field(
        default=None,
        description="Reason why generation finished"
    )


class ChatStreamRequest(BaseModel):
    """Request model for streaming chat endpoint."""
    message: str = Field(..., description="User message to send to the AI", min_length=1)
    history: Optional[List[ChatMessage]] = Field(
        default=None, 
        description="Previous conversation history"
    )
    model: Optional[str] = Field(
        default=None, 
        description="Model to use for generation"
    )
    temperature: Optional[float] = Field(
        default=None, 
        ge=0.0, 
        le=2.0, 
        description="Controls randomness in generation"
    )
    system_instruction: Optional[str] = Field(
        default=None,
        description="System instruction to guide the model's behavior"
    )


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    model: str


# ============================================
# Speech-to-Text Schemas
# ============================================

class SpeechTranscribeRequest(BaseModel):
    """Request model for transcribing audio file."""
    language_code: Optional[str] = Field(
        default=None,
        description="Language code (e.g., 'en-US', 'zh-CN')"
    )
    sample_rate: Optional[int] = Field(
        default=None,
        gt=0,
        description="Audio sample rate in Hz"
    )
    enable_automatic_punctuation: Optional[bool] = Field(
        default=None,
        description="Enable automatic punctuation"
    )


class SpeechStreamRequest(BaseModel):
    """Request model for streaming speech transcription."""
    language_code: Optional[str] = Field(
        default=None,
        description="Language code (e.g., 'en-US', 'zh-CN')"
    )
    single_utterance: Optional[bool] = Field(
        default=None,
        description="Stop listening after single utterance"
    )
    duration_seconds: Optional[int] = Field(
        default=None,
        gt=0,
        description="Maximum recording duration in seconds"
    )


class SpeechTranscriptionResult(BaseModel):
    """Result model for speech transcription."""
    transcript: str = Field(..., description="Transcribed text")
    is_final: Optional[bool] = Field(
        default=None,
        description="Whether this is a final result"
    )
    confidence: Optional[float] = Field(
        default=None,
        description="Confidence score (0-1) for final results"
    )
    stability: Optional[float] = Field(
        default=None,
        description="Stability score (0-1) for interim results"
    )


class SpeechTranscriptionResponse(BaseModel):
    """Response model for speech transcription."""
    transcript: str = Field(..., description="Final transcribed text")
    confidence: Optional[float] = Field(
        default=None,
        description="Confidence score (0-1)"
    )
    language_code: str = Field(..., description="Language code used")
    sample_rate: int = Field(..., description="Sample rate used (Hz)")
