"""
Pydantic schemas for AI chat API.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


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
