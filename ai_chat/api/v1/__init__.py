"""
API v1 routes for AI chat.
"""
from fastapi import APIRouter
from .chat import router as chat_router
from .speech import router as speech_router

# Create main v1 router
router = APIRouter(prefix="/v1")

# Include sub-routers
router.include_router(chat_router)
router.include_router(speech_router)

__all__ = ["router"]

