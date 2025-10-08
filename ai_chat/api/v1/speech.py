"""
API routes for Speech-to-Text functionality.
"""
import logging
import json
from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File
from fastapi.responses import StreamingResponse

from ...models.schemas import (
    SpeechTranscribeRequest,
    SpeechStreamRequest,
    SpeechTranscriptionResponse,
    HealthCheckResponse
)
from ...services.speech_service import SpeechToTextService, get_speech_service
from ...config import ChatConfig

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/speech", tags=["Speech-to-Text"])


@router.post("/transcribe", response_model=SpeechTranscriptionResponse)
async def transcribe_audio_file(
    file: UploadFile = File(..., description="Audio file to transcribe"),
    language_code: str = None,
    sample_rate: int = None,
    enable_automatic_punctuation: bool = None,
    service: SpeechToTextService = Depends(get_speech_service)
):
    """
    Transcribe an audio file to text.
    
    Args:
        file: Audio file (WAV, LINEAR16 format recommended)
        language_code: Language code (e.g., 'en-US', 'zh-CN')
        sample_rate: Audio sample rate in Hz
        enable_automatic_punctuation: Enable automatic punctuation
        service: Injected speech service
        
    Returns:
        SpeechTranscriptionResponse with transcribed text
        
    Raises:
        HTTPException: If transcription fails
    """
    try:
        # Read audio content
        audio_content = await file.read()
        
        if not audio_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty audio file"
            )
        
        # Transcribe audio
        result = service.transcribe_audio_file(
            audio_content=audio_content,
            language_code=language_code,
            sample_rate=sample_rate,
            enable_automatic_punctuation=enable_automatic_punctuation,
        )
        
        return SpeechTranscriptionResponse(
            transcript=result['transcript'],
            confidence=result.get('confidence'),
            language_code=language_code or ChatConfig.SPEECH_LANGUAGE_CODE,
            sample_rate=sample_rate or ChatConfig.SPEECH_SAMPLE_RATE,
        )
        
    except Exception as e:
        logger.error(f"Transcription endpoint error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to transcribe audio: {str(e)}"
        )


@router.post("/stream/microphone")
async def stream_microphone_transcription(
    request: SpeechStreamRequest,
    service: SpeechToTextService = Depends(get_speech_service)
):
    """
    Start streaming transcription from microphone.
    
    This endpoint captures audio from the server's microphone and streams
    transcription results in real-time. Each line in the response is a JSON
    object with the transcription result.
    
    Args:
        request: Speech stream configuration
        service: Injected speech service
        
    Returns:
        StreamingResponse with transcription results as JSON lines
        
    Raises:
        HTTPException: If streaming fails
    """
    try:
        def generate():
            """Generator function for streaming transcription."""
            try:
                for result in service.capture_and_transcribe_microphone(
                    duration_seconds=request.duration_seconds,
                    language_code=request.language_code,
                    single_utterance=request.single_utterance,
                ):
                    # Send result as JSON line
                    yield json.dumps(result) + "\n"
                    
            except Exception as e:
                logger.error(f"Microphone streaming error: {str(e)}")
                error_result = {
                    'error': str(e),
                    'transcript': '',
                    'is_final': True
                }
                yield json.dumps(error_result) + "\n"
        
        return StreamingResponse(
            generate(),
            media_type="application/x-ndjson",  # Newline-delimited JSON
        )
        
    except Exception as e:
        logger.error(f"Stream endpoint error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start streaming: {str(e)}"
        )


@router.post("/stream/upload")
async def stream_audio_upload_transcription(
    file: UploadFile = File(..., description="Audio file to transcribe"),
    language_code: str = None,
    single_utterance: bool = False,
    service: SpeechToTextService = Depends(get_speech_service)
):
    """
    Stream transcription of an uploaded audio file.
    
    This endpoint transcribes an uploaded audio file using streaming recognition,
    providing interim and final results.
    
    Args:
        file: Audio file (WAV, LINEAR16 format recommended)
        language_code: Language code (e.g., 'en-US', 'zh-CN')
        single_utterance: Stop after single utterance
        service: Injected speech service
        
    Returns:
        StreamingResponse with transcription results as JSON lines
        
    Raises:
        HTTPException: If streaming fails
    """
    try:
        # Read audio content
        audio_content = await file.read()
        
        if not audio_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty audio file"
            )
        
        # Create a generator that yields chunks
        chunk_size = 1024
        def audio_chunks():
            """Generator that yields audio chunks."""
            for i in range(0, len(audio_content), chunk_size):
                yield audio_content[i:i + chunk_size]
        
        def generate():
            """Generator function for streaming transcription."""
            try:
                for result in service.transcribe_audio_stream(
                    audio_generator=audio_chunks(),
                    language_code=language_code,
                    single_utterance=single_utterance,
                ):
                    # Send result as JSON line
                    yield json.dumps(result) + "\n"
                    
            except Exception as e:
                logger.error(f"Audio streaming error: {str(e)}")
                error_result = {
                    'error': str(e),
                    'transcript': '',
                    'is_final': True
                }
                yield json.dumps(error_result) + "\n"
        
        return StreamingResponse(
            generate(),
            media_type="application/x-ndjson",  # Newline-delimited JSON
        )
        
    except Exception as e:
        logger.error(f"Stream upload endpoint error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start streaming: {str(e)}"
        )


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(service: SpeechToTextService = Depends(get_speech_service)):
    """
    Check the health status of the Speech-to-Text service.
    
    Args:
        service: Injected speech service
    
    Returns:
        HealthCheckResponse with service status
    """
    try:
        health = service.check_health()
        # Return in the format expected by HealthCheckResponse
        return HealthCheckResponse(
            status=health['status'],
            service=health['service'],
            model=health['language']  # Use language as model field
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: {str(e)}"
        )

