from fastapi import APIRouter
from .search import router as search_router
from .rank import router as rank_router
from .book import router as book_router
from .chat import router as chat_router
from .speech import router as speech_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(search_router, tags=["search"])
api_router.include_router(rank_router, tags=["rank"])
api_router.include_router(book_router, tags=["book"])
api_router.include_router(chat_router, tags=["AI Chat"])
api_router.include_router(speech_router, tags=["Speech-to-Text"])
