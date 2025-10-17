from fastapi import APIRouter
from .search import router as search_router
from .rank import router as rank_router
from .book import router as book_router
from .chat import router as chat_router
from .speech import router as speech_router
from .telephony import router as telephony_router

# Main API router - prefix is added in main.py
api_router = APIRouter(prefix="/v1")
api_router.include_router(search_router, prefix="/search", tags=["search"])
api_router.include_router(rank_router, prefix="/rank", tags=["rank"])
api_router.include_router(book_router, prefix="/book", tags=["book"])
api_router.include_router(chat_router, prefix="/chat", tags=["AI Chat"])  # tags already defined in chat.py
api_router.include_router(speech_router, prefix="/speech", tags=["Speech-to-Text"])
api_router.include_router(telephony_router, prefix="/telephony", tags=["Telephony"])