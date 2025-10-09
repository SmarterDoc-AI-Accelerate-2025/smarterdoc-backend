"""
API routes for AI chat functionality.
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import StreamingResponse

from app.models.schemas import (
    ChatRequest, 
    ChatResponse, 
    ChatStreamRequest,
    HealthCheckResponse
)
from app.services.chat_service import GenAIChatService
from app.deps import get_chat_service

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/chat", tags=["AI Chat"])


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    service: GenAIChatService = Depends(get_chat_service)
):
    """
    Send a message to the AI and get a response.
    
    Args:
        request: Chat request with message and optional history
        service: Injected chat service
        
    Returns:
        ChatResponse with AI-generated message
        
    Raises:
        HTTPException: If generation fails
    """
    try:
        result = await service.generate_response(
            message=request.message,
            history=request.history,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            system_instruction=request.system_instruction,
        )
        
        return ChatResponse(
            message=result['message'],
            model_used=result['model_used'],
            usage=result.get('usage'),
            finish_reason=result.get('finish_reason'),
        )
        
    except Exception as e:
        logger.error(f"Chat endpoint error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate response: {str(e)}"
        )


@router.post("/stream")
async def chat_stream(
    request: ChatStreamRequest,
    service: GenAIChatService = Depends(get_chat_service)
):
    """
    Send a message to the AI and get a streaming response.
    
    Args:
        request: Chat stream request with message and optional history
        service: Injected chat service
        
    Returns:
        StreamingResponse with AI-generated text chunks
        
    Raises:
        HTTPException: If generation fails
    """
    try:
        async def generate():
            """Generator function for streaming response."""
            try:
                async for chunk in service.generate_response_stream(
                    message=request.message,
                    history=request.history,
                    model=request.model,
                    temperature=request.temperature,
                    system_instruction=request.system_instruction,
                ):
                    yield chunk
            except Exception as e:
                logger.error(f"Streaming error: {str(e)}")
                yield f"\n\nError: {str(e)}"
        
        return StreamingResponse(
            generate(),
            media_type="text/plain",
        )
        
    except Exception as e:
        logger.error(f"Chat stream endpoint error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start streaming: {str(e)}"
        )


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(service: GenAIChatService = Depends(get_chat_service)):
    """
    Check the health status of the AI chat service.
    
    Args:
        service: Injected chat service
    
    Returns:
        HealthCheckResponse with service status
    """
    try:
        health = service.check_health()
        return HealthCheckResponse(**health)
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: {str(e)}"
        )

